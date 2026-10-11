"""Windows-friendly, project-relative startup with artifact compatibility checks."""
from pathlib import Path
import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'reports' / '.matplotlib'))


def prepare(force=False):
    from ml.features import FEATURE_COLUMNS
    from ml.train_model import fingerprint
    import sklearn
    data = ROOT / 'data'
    metadata_path = data / 'dataset_metadata.json'
    compatible = False
    try:
        meta = json.loads(metadata_path.read_text())
        compatible = meta['schema_version']==2 and meta['total_days']>=210 and all((data/name).exists() for name in ['customers.csv','notifications.csv','subscription_events.csv','order_events.csv'])
    except (OSError, ValueError, KeyError): pass
    if force or not compatible:
        print('Preparing reproducible 210-day synthetic data...')
        from data.generate_data import generate_dataset
        generate_dataset(data, ROOT / 'reports')
    import joblib
    model_ok = False
    try:
        bundle = joblib.load(ROOT / 'models/risk_model.joblib')
        meta = bundle['metadata']
        model_ok = meta['schema_version']==2 and meta['feature_schema']==FEATURE_COLUMNS and meta['dataset_fingerprint']==fingerprint(data) and meta['versions']['sklearn']==sklearn.__version__ and (ROOT / 'reports/evaluation.json').exists()
    except Exception: pass
    if force or not model_ok:
        print('Model missing or incompatible with data/schema/dependencies. Training...')
        from ml.train_model import build_snapshots, train_and_evaluate
        train_and_evaluate(build_snapshots(data), ROOT / 'models', ROOT / 'reports')
    print('Dataset fingerprint, feature schema, and scikit-learn version verified.')


def main():
    parser = argparse.ArgumentParser(description='ShopEasy local synthetic-data demonstration')
    parser.add_argument('--port',type=int,default=int(os.environ.get('SHOPEASY_PORT','8000')))
    parser.add_argument('--prepare',action='store_true',help='Regenerate data/model/reports and exit')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not 1<=args.port<=65535: parser.error('Port must be between 1 and 65535')
    if not args.prepare:
        with socket.socket() as sock:
            try: sock.bind(('127.0.0.1',args.port))
            except OSError:
                parser.exit(1,f'Port {args.port} is already in use. Stop the other server or run python run.py --port {args.port+1 if args.port<65535 else 8001}\n')
    try: prepare(args.prepare)
    except Exception as exc:
        parser.exit(1,f'Artifact preparation failed: {exc}\nCheck the virtual environment, requirements.txt, and data/models/reports write permissions.\n')
    if args.prepare: return
    url=f'http://127.0.0.1:{args.port}'
    print(f'ShopEasy: {url}\nSynthetic-data demonstration. Press Ctrl+C to stop.')
    def browser_when_ready():
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            try:
                with urllib.request.urlopen(url+'/api/health',timeout=1) as response:
                    if json.load(response)['status']=='ok':
                        if not args.no_browser: webbrowser.open(url)
                        return
            except Exception: time.sleep(.25)
        print(f'Health check timed out. Check server errors; open {url} after resolving them.')
    threading.Thread(target=browser_when_ready,daemon=True).start()
    import uvicorn
    uvicorn.run('app:app',host='127.0.0.1',port=args.port,reload=False)

if __name__=='__main__': main()
