"""Only persist the non-secret upload ledger; never tokens, config or media."""
import os, sqlite3, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'.state/jobs.sqlite3'
target=root/'runtime/jobs.sqlite3'
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('This persistence hook is for GitHub Actions only.')
if not source.exists():raise SystemExit('No ledger to persist.')
target.parent.mkdir(exist_ok=True)
with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:src.backup(dst)
def run(*args):subprocess.run(args,cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
run('git','config','user.name','github-actions[bot]')
run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
run('git','add','--','runtime/jobs.sqlite3')
result=subprocess.run(['git','diff','--cached','--quiet','--','runtime/jobs.sqlite3'],cwd=root)
if result.returncode==1:
    run('git','commit','-m','Persist Shorts upload ledger','--','runtime/jobs.sqlite3')
    run('git','push','origin','HEAD')
elif result.returncode!=0:raise SystemExit('Cannot inspect ledger changes.')
