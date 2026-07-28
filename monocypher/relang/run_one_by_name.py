import sys, os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 2:
    print('Usage: run_one_by_name.py <input_basename.json>')
    sys.exit(1)
name = sys.argv[1]
test = os.path.join(HERE, 'input', name)
expected = os.path.join(HERE, 'output', name)
if not os.path.exists(test):
    print('test not found:', test); sys.exit(1)
with open(test) as f:
    tc = json.load(f)
with open(expected) as f:
    exp = json.load(f)
cmd = ['python', os.path.abspath(os.path.join(HERE, '..', 'target', 'main.py'))]
print('Running', name)
print('data repr:', repr(tc['data']))
try:
    r = subprocess.run(cmd, input=tc['data'], capture_output=True, text=True, timeout=30)
except Exception as e:
    print('subproc exec error', e); raise
print('returncode', r.returncode)
print('stdout repr', repr(r.stdout))
print('stderr repr', repr(r.stderr))
with open(os.path.join(HERE, name + '.stdout.txt'), 'w', encoding='utf-8') as f:
    f.write(r.stdout)
with open(os.path.join(HERE, name + '.stderr.txt'), 'w', encoding='utf-8') as f:
    f.write(r.stderr)
