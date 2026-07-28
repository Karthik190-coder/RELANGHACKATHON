import os, json, glob, hashlib, subprocess, shlex
HERE = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(HERE, 'input')
output_dir = os.path.join(HERE, 'output')
files = sorted(glob.glob(os.path.join(input_dir, '*.json')))
cmd = shlex.split('python d:\\\\RELANGHACKATHON\\\\deliverables\\\\monocypher\\\\target\\\\main.py')
passed=0
for f in files[:20]:
    with open(f) as fp:
        tc=json.load(fp)
    expected_path = os.path.join(output_dir, os.path.basename(f))
    with open(expected_path) as fp:
        expected=json.load(fp)
    expected_hash = hashlib.sha256(expected['output'].encode('utf-8')).hexdigest()
    r = subprocess.run(cmd, input=tc['data'], capture_output=True, text=True, timeout=30)
    actual_hash = hashlib.sha256(r.stdout.encode('utf-8')).hexdigest()
    ok = actual_hash==expected_hash
    print(os.path.basename(f), 'PASS' if ok else 'FAIL')
    if ok: passed+=1
print('\nResult:', passed, '/', min(20,len(files)))