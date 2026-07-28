import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
test = os.path.join(HERE, 'input', '01_verify_0003.json')
expected = os.path.join(HERE, 'output', '01_verify_0003.json')
cmd = ['python', os.path.abspath(os.path.join(HERE, '..', 'target', 'main.py'))]

with open(test) as f:
    tc = json.load(f)
with open(expected) as f:
    exp = json.load(f)

print('--- test id:', tc['id'])
print('--- data repr:')
print(repr(tc['data']))
print('--- expected output repr:')
print(repr(exp['output']))

try:
    r = subprocess.run(cmd, input=tc['data'], capture_output=True, text=True, timeout=10)
except Exception as e:
    print('Subprocess error:', e)
    raise

print('--- returncode:', r.returncode)
print('--- stdout repr:')
print(repr(r.stdout))
print('--- stdout bytes:')
print(r.stdout.encode('utf-8'))
print('--- stderr repr:')
print(repr(r.stderr))

# write outputs for later inspection
with open(os.path.join(HERE, 'last_stdout.txt'), 'wb') as f:
    f.write(r.stdout.encode('utf-8'))
with open(os.path.join(HERE, 'last_stderr.txt'), 'wb') as f:
    f.write(r.stderr.encode('utf-8'))
