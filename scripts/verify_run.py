import json,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
p=Path(__file__).resolve().parents[1]/'dist/data/results.json'
if not p.exists(): sys.exit(1)
d=json.loads(p.read_text(encoding='utf-8'))
ts=d.get('generated_at')
if not ts or datetime.fromisoformat(ts).astimezone(ZoneInfo('Asia/Seoul')).date()!=datetime.now(ZoneInfo('Asia/Seoul')).date(): sys.exit(1)
if d.get('status') not in ('ok','partial'): sys.exit(1)
print('today result exists')
