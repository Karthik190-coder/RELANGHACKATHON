import os, json, glob, subprocess, shlex, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(HERE, 'input')
output_dir = os.path.join(HERE, 'output')
files = sorted(glob.glob(os.path.join(input_dir, '*.json')))
import os
cmd = ['python', os.path.abspath(os.path.join(HERE, '..', 'target', 'main.py'))]

for fpath in files[:10]:
    with open(fpath) as f:
        tc = json.load(f)
    with open(os.path.join(output_dir, os.path.basename(fpath))) as f:
        expected = json.load(f)
    print('---', os.path.basename(fpath))
    try:
        r = subprocess.run(cmd, input=tc['data'], capture_output=True, text=True, timeout=10)
    except Exception as e:
        print('EXC', e)
        continue
    ah = hashlib.sha256(r.stdout.encode('utf-8')).hexdigest()
    eh = hashlib.sha256(expected['output'].encode('utf-8')).hexdigest()
    print('returncode', r.returncode)
    print('stdout repr', repr(r.stdout))
    print('stderr repr', repr(r.stderr))
    print('match', ah == eh)
