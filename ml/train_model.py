"""Purged chronological model selection on synthetic future customer snapshots."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import hashlib
import json
import platform
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score, average_precision_score, RocCurveDisplay, PrecisionRecallDisplay
from ml.features import FEATURE_COLUMNS, normalize_event, extract_snapshot_features_from_events
SEED = 42
HORIZON = 14
MIN_EXPOSURE = 5
SPLITS = {'train': [21, 98], 'validation': [119, 147], 'test': [168, 196]}


def fingerprint(data_dir):
    digest = hashlib.sha256()
    for name in ['customers.csv', 'notifications.csv', 'subscription_events.csv', 'order_events.csv', 'dataset_metadata.json']:
        digest.update((Path(data_dir) / name).read_bytes())
    return digest.hexdigest()


def future_label(events, subscriptions, day, observation_end):
    if day + HORIZON > observation_end:
        return None
    if any(day <= e['day'] < day + HORIZON for e in subscriptions):
        return 1
    future = [e for e in events if day <= e['day'] < day + HORIZON and e['notification_type'] != 'order_update']
    if len(future) < MIN_EXPOSURE:
        return None
    return int(sum(e['action'] == 'opened' for e in future) / len(future) < .05)


def build_snapshots(data_dir=ROOT / 'data'):
    data_dir = Path(data_dir)
    meta = json.loads((data_dir / 'dataset_metadata.json').read_text())
    notifications = pd.read_csv(data_dir / 'notifications.csv')
    subscriptions = pd.read_csv(data_dir / 'subscription_events.csv')
    records = []
    for cid, group in notifications.groupby('customer_id'):
        events = sorted([normalize_event(e) for e in group.to_dict('records')], key=lambda e: e['day'])
        subs = subscriptions[subscriptions.customer_id == cid].to_dict('records')
        for day in range(21, meta['total_days'], 7):
            if any(e['day'] < day for e in subs):
                continue
            features = extract_snapshot_features_from_events(events, day)
            records.append(dict(features, customer_id=cid, snapshot_day=day, label=future_label(events, subs, day, meta['total_days'])))
    df = pd.DataFrame(records)
    df.attrs['dataset_fingerprint'] = fingerprint(data_dir)
    df.attrs['dataset'] = meta
    return df


def metrics(y, probability, threshold):
    pred = probability >= threshold
    return {'accuracy': accuracy_score(y, pred), 'precision': precision_score(y, pred, zero_division=0), 'recall': recall_score(y, pred, zero_division=0), 'f1': f1_score(y, pred, zero_division=0), 'confusion_matrix': confusion_matrix(y, pred, labels=[0,1]).tolist(), 'roc_auc': roc_auc_score(y, probability) if len(set(y)) == 2 else None, 'pr_auc': average_precision_score(y, probability) if len(set(y)) == 2 else None}


def train_and_evaluate(snap_df, models_dir=ROOT / 'models', reports_dir=ROOT / 'reports'):
    models_dir, reports_dir = Path(models_dir), Path(reports_dir)
    models_dir.mkdir(exist_ok=True, parents=True)
    reports_dir.mkdir(exist_ok=True, parents=True)
    known = snap_df.dropna(subset=['label'])
    parts = {name: known[known.snapshot_day.between(*bounds)] for name, bounds in SPLITS.items()}
    train, validation, test = [parts[name] for name in ['train','validation','test']]
    assert train.snapshot_day.max() + HORIZON < validation.snapshot_day.min()
    assert validation.snapshot_day.max() + HORIZON < test.snapshot_day.min()
    if any(len(p) == 0 or p.label.nunique() < 2 for p in parts.values()):
        raise ValueError('Insufficient chronological data or classes; generate the documented 210-day dataset.')
    # A fixed chronological validation block tunes hyperparameters AND thresholds.
    # No repeated customer snapshots are randomly shuffled into tuning folds.
    candidates = [('Dummy prior', DummyClassifier(strategy='prior'))]
    candidates += [(f'Logistic Regression C={c}', make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1500, class_weight='balanced', random_state=SEED))) for c in [.1, 1, 10]]
    candidates += [(f'Decision Tree depth={d}', DecisionTreeClassifier(max_depth=d, min_samples_leaf=20, class_weight='balanced', random_state=SEED)) for d in [3,5,7]]
    candidates += [(f'KNN k={k}', make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=k))) for k in [5,11,21]]
    results, fitted = [], {}
    for name, model in candidates:
        model.fit(train[FEATURE_COLUMNS], train.label.astype(int))
        p = model.predict_proba(validation[FEATURE_COLUMNS])[:, list(model.classes_).index(1)]
        choices = [(metrics(validation.label, p, t), float(t)) for t in np.arange(.15, .86, .05)]
        score, threshold = max(choices, key=lambda x: (x[0]['f1'], x[0]['recall'], x[1]))
        results.append({'model': name, 'threshold': threshold, **score})
        fitted[name] = model
    selected = max(results, key=lambda r: (r['f1'], r['recall']))
    model = fitted[selected['model']]
    threshold = selected['threshold']
    # Final test is touched only after all selection is frozen. No refitting on validation.
    probability = model.predict_proba(test[FEATURE_COLUMNS])[:, list(model.classes_).index(1)]
    final = metrics(test.label, probability, threshold)
    explanation = {'kind': 'unavailable', 'values': {}}
    estimator = model.steps[-1][1] if hasattr(model, 'steps') else model
    if hasattr(estimator, 'coef_'):
        explanation = {'kind': 'global standardized logistic coefficients (log odds; not causal)', 'values': dict(zip(FEATURE_COLUMNS, estimator.coef_[0].tolist()))}
    elif hasattr(estimator, 'feature_importances_'):
        explanation = {'kind': 'global tree impurity importance (not individual attribution)', 'values': dict(zip(FEATURE_COLUMNS, estimator.feature_importances_.tolist()))}
    metadata = {'schema_version': 2, 'feature_schema': FEATURE_COLUMNS, 'dataset_fingerprint': snap_df.attrs['dataset_fingerprint'], 'training_time': datetime.now(timezone.utc).isoformat(), 'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'joblib': joblib.__version__}, 'splits': SPLITS, 'horizon_days': HORIZON, 'min_future_exposure': MIN_EXPOSURE, 'model_name': selected['model'], 'validation_thresholds': {'medium': threshold / 2, 'high': threshold}, 'probabilities_calibrated': False}
    report = {'metadata': metadata, 'dataset': snap_df.attrs['dataset'], 'counts': {'all_snapshots': len(snap_df), 'unknown_snapshots': int(snap_df.label.isna().sum()), 'purged_known_snapshots': int(len(known) - sum(len(p) for p in parts.values())), 'splits': {n: {'count': len(p), 'positive': int(p.label.sum()), 'negative': int(len(p) - p.label.sum()), 'first_day': int(p.snapshot_day.min()), 'last_day': int(p.snapshot_day.max()), 'latest_outcome_end': int(p.snapshot_day.max()+HORIZON)} for n,p in parts.items()}}, 'validation_comparison': results, 'selected_test': final, 'feature_explanation': explanation}
    joblib.dump({'model': model, 'metadata': metadata}, models_dir / 'risk_model.joblib')
    (models_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (reports_dir / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    snap_df.to_csv(reports_dir / 'snapshots.csv', index=False)
    text = '# Synthetic disengagement risk evaluation\n\nTarget: explicit promotional unsubscribe within 14 days, or <5% opens with at least 5 future promotional exposures and complete 14-day follow-up. Otherwise unknown; prior unsubscribe snapshots excluded. This does not measure psychological fatigue or shopping churn.\n\n'
    text += 'Selection and tuning use a fixed time-aware validation block, with 21 days between partition snapshot boundaries (14-day outcomes fully mature). Final held-out test evaluates only the selected model, once. Preprocessing is fitted on training only.\n\n'
    text += '```json\n' + json.dumps(report, indent=2) + '\n```\n\n'
    text += 'PR-AUC is reported as average precision. Probabilities are not calibrated. This evaluates future snapshots of existing synthetic customers, not entirely unseen customers. An unseen-customer evaluation requires a separate group holdout. Repeated snapshots are correlated; metrics are descriptive, not independent-sample confidence estimates. Persona is excluded from features. Global coefficients/importances are model-specific; planner reasons are policy rules, not model attributions.\n'
    (reports_dir / 'model_report.md').write_text(text, encoding='utf-8')
    fig, axes = plt.subplots(1,3, figsize=(13,4))
    axes[0].imshow(final['confusion_matrix'], cmap='Blues')
    for i in range(2):
        for j in range(2): axes[0].text(j,i,str(final['confusion_matrix'][i][j]),ha='center')
    axes[0].set(xlabel='Predicted', ylabel='Actual', title='Final test confusion matrix', xticks=[0,1], yticks=[0,1])
    RocCurveDisplay.from_predictions(test.label, probability, ax=axes[1])
    PrecisionRecallDisplay.from_predictions(test.label, probability, ax=axes[2])
    fig.tight_layout()
    fig.savefig(reports_dir / 'evaluation.png', dpi=140)
    plt.close(fig)
    print(json.dumps({'selected': selected['model'], 'test': final, 'counts': report['counts']}, indent=2))
    return model

if __name__ == '__main__':
    train_and_evaluate(build_snapshots())
