import os, json, glob, hashlib, subprocess, shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(HERE, 'input')
output_dir = os.path.join(HERE, 'output')
files = sorted(glob.glob(os.path.join(input_dir, '*.json')))
cmd = shlex.split('python d:\\\\RELANGHACKATHON\\\\deliverables\\\\monocypher\\\\target\\\\main.py')

def run_one(fpath):
    with open(fpath) as fp:
        tc=json.load(fp)
    with open(os.path.join(output_dir, os.path.basename(fpath))) as fp:
        expected=json.load(fp)
    expected_hash=hashlib.sha256(expected['output'].encode('utf-8')).hexdigest()
    try:
        r=subprocess.run(cmd, input=tc['data'], capture_output=True, text=True, timeout=30)
        actual_hash=hashlib.sha256(r.stdout.encode('utf-8')).hexdigest()
        return os.path.basename(fpath), actual_hash==expected_hash, r.stdout, r.stderr
    except Exception as e:
        return os.path.basename(fpath), False, '', str(e)

files_to_run = files[:100]
results = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(run_one,f) for f in files_to_run]
    for f in as_completed(futures):
        results.append(f.result())

pass_count = sum(1 for _,ok,_,_ in results if ok)
print('Passed:', pass_count, '/', len(files_to_run))
for name, ok, out, err in results[:10]:
    print(name, 'PASS' if ok else 'FAIL')
    if not ok:
        print('stdout repr:', repr(out))
        print('stderr repr:', repr(err))
        break
