"""Offline PDF reporting; does not change simulation or policy state."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak

NAMES = {'offer': 'Offers & Sales', 'new_arrival': 'New Arrivals', 'price_drop': 'Price Drops', 'order_update': 'Order Updates'}
FONT_DIR = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('Report', str(FONT_DIR / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('ReportBold', str(FONT_DIR / 'VeraBd.ttf')))
pdfmetrics.registerFontFamily('Report', normal='Report', bold='ReportBold')


def customer_pdf(c):
    output = BytesIO()
    styles = getSampleStyleSheet()
    for key in ('Normal', 'BodyText', 'Heading1', 'Heading2', 'Heading3', 'Title'):
        styles[key].fontName = 'ReportBold' if key.startswith('Heading') or key == 'Title' else 'Report'
        styles[key].textColor = colors.HexColor('#0F172A')
    for key in ('Heading1', 'Heading2', 'Heading3'):
        styles[key].keepWithNext = True
    styles['BodyText'].fontSize, styles['BodyText'].leading = 9.5, 14
    styles['BodyText'].spaceAfter = 7
    styles['Title'].fontSize, styles['Title'].leading, styles['Title'].alignment = 23, 29, TA_LEFT
    styles['Heading2'].fontSize, styles['Heading2'].leading = 15, 20
    styles['Heading2'].spaceBefore = 17
    small = ParagraphStyle('Cell', parent=styles['BodyText'], fontSize=8, leading=12, spaceAfter=0, splitLongWords=True)
    story = []
    def para(value, style='BodyText'):
        text = str(value).replace('\u2013', '-').replace('\u2014', '-').replace('\u2011', '-')
        return Paragraph(escape(text).replace('\n', '<br/>'), styles[style] if isinstance(style, str) else style)
    def add(value, style='BodyText'):
        story.append(para(value, style))
    def heading(text):
        add(text, 'Heading2')
    def table(headers, rows, widths):
        if not rows:
            add('No records available.')
            return
        data = [[para(h, small) for h in headers]] + [[para(v, small) for v in row] for row in rows]
        result = Table(data, colWidths=[w*mm for w in widths], repeatRows=1, hAlign='LEFT', splitInRow=1)
        result.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EEF2FF')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LINEBELOW', (0,0), (-1,-1), .4, colors.HexColor('#E2E8F0')),
            ('LEFTPADDING', (0,0), (-1,-1), 7), ('RIGHTPADDING', (0,0), (-1,-1), 7),
            ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ]))
        story.extend([result, Spacer(1, 8)])
    prefs, a = c['preferences'], c['analysis']
    def time(value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo(prefs['timezone'])).strftime('%d %b %Y, %H:%M') if value else 'Not scheduled'
    def probability(value):
        return 'Unavailable' if value is None else f'{value:.1%} (uncalibrated)'
    generated = datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')
    add('SHOPEASY / SYNTHETIC CUSTOMER REPORT', 'Heading3')
    add(c['name'], 'Title')
    add('Send less. Mean more.')
    add(f"Generated {generated} | Current week {c['current_week']} | {len(c['history'])} completed weeks")
    add(f"Schedule timezone: {prefs['timezone']}. All interactions are simulated; no real notifications were sent.")
    heading('Customer summary')
    add(c['role_hint'])
    table(['Status', 'Policy risk', 'Observed trend', 'Upcoming schedule'], [[a['status_label'], a['risk_level'], a['trend'], f"{len(c['active_week_notifications'])} messages; promotional limit {a['frequency']}/week"]], [46,30,45,57])
    heading('1. Observed behavior')
    for item in a['observations']: add(item)
    table(['Week', 'Delivered', 'Opened', 'Clicked', 'Saved', 'Delivery policy'], [[h['week'], len(h['notifications']), sum(n['action']=='opened' for n in h['notifications']), sum(bool(n.get('clicked')) for n in h['notifications']), sum(bool(n.get('saved')) for n in h['notifications']), h.get('delivery_policy','adaptive')] for h in c['history']], [17,25,25,25,25,61])
    add('Category interest: opened / delivered in the recent 21-day window. No exposure means unknown.')
    table(['Category', 'Interest score', 'Description', 'Exposures'], [[NAMES[t], f"{x['score']:.3f}" if x['exposures'] else 'Unknown', x['level'], x['exposures']] for t,x in a['interests'].items()], [65,40,43,30])
    heading('2. ML estimate')
    add(f"Model output: {probability(a['model_probability'])}. Model tier: {a['model_risk_tier']}.")
    add(a['prediction_status'])
    add('This estimates future promotional disengagement. It is not individual model accuracy, proof of psychological fatigue, or shopping churn.')
    add(a['model_explanation']['kind'])
    heading('3. Sending-policy decisions')
    add(f"Policy tier: {a['risk_level']}. Combines the ML estimate with behavioral rules and explicit preferences.")
    for item in a['policy_overrides']: add(item)
    table(['Category', 'Decision', 'Reason'], [[NAMES[x['type']], label, x['reason']] for label, items in [('Continued',a['continued_types']),('Paused',a['paused_types'])] for x in items], [45,28,105])
    add('Suggested next action (advice): '+a['recommended_action']+'. This recommendation does not send a message.')
    heading('4. Explicit customer preferences')
    table(['Preference', 'Value'], [[key.replace('_',' ').title(), ', '.join(NAMES.get(x,x) for x in value) or 'None' if isinstance(value,list) else str(value)] for key,value in prefs.items()], [70,108])
    heading(f"5. Upcoming week {c['current_week']} notification plan")
    for n in c['planner']:
        add(f"{NAMES[n['type']]} | {n['status'].title()} | {time(n['scheduled_at'])}", 'Heading3')
        add(n['text'])
        add('Reason: '+n['reason'])
    add('Baseline comparison: same candidates and upcoming week; counts below are promotional candidates only.')
    table(['Plan', 'Allowed', 'Deferred', 'Suppressed'], [[key.title(), *[c['comparison'][key][status] for status in ['allowed','deferred','suppressed']]] for key in ['baseline','adaptive']], [65,37,38,38])
    add(c['comparison']['note'])
    if c['history']:
        story.append(PageBreak())
    heading('6. Recorded interactions')
    if not c['history']: add('No interactions recorded yet. Simulate a week to gather evidence.')
    for h in c['history']:
        week_title = para(f"Week {h['week']} | {len(h['notifications'])} recorded deliveries", 'Heading3')
        if not h['notifications']:
            story.append(KeepTogether([week_title, para('No eligible notifications delivered in this week.')]))
        for i, n in enumerate(h['notifications']):
            story.append(KeepTogether(([week_title] if i == 0 else []) + [
                para(f"{NAMES[n['type']]} | {time(n['timestamp'])} | {n['action'].title()}"),
                para(n['text']),
                para(f"Simulated viewing: {n.get('view_seconds',0)} seconds; timing: {n.get('timing','right_away')}; clicked: {bool(n.get('clicked'))}; saved: {bool(n.get('saved'))}."),
            ]))
    heading('7. Audited decision history')
    table(['Week', 'Policy tier', 'Model output', 'Scheduled / suppressed'], [[log['week'], log['prediction']['risk_level'], probability(log['prediction']['model_probability']), f"{sum(bool(n['scheduled_at']) for n in log['decisions'])} scheduled / {sum(n['status']=='suppressed' for n in log['decisions'])} suppressed"] for log in c['decision_history']], [20,35,65,58])
    heading('Limitations')
    for line in [
        'All customers, notifications, interactions and training data are synthetic.',
        'Viewing durations and response timing are simulated, not measured.',
        'Model probabilities are uncalibrated. Low interaction does not establish fatigue or shopping churn.',
        'A planned reduction is not evidence of improved retention or wellbeing. Suppressed messages have no imagined responses.',
        'This report captures a snapshot. Later interactions or preferences can change the plan.',
    ]: add(line)
    def footer(canvas, doc):
        canvas.setTitle('ShopEasy customer report - '+c['name'])
        canvas.setAuthor('ShopEasy Smart Notifications')
        canvas.setFont('Report', 8)
        canvas.setFillColor(colors.HexColor('#475569'))
        canvas.drawString(16*mm, 10*mm, 'ShopEasy | Synthetic simulation | '+c['name'])
        canvas.drawRightString(194*mm, 10*mm, f'Page {doc.page}')
    SimpleDocTemplate(output, pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=17*mm, bottomMargin=18*mm).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
