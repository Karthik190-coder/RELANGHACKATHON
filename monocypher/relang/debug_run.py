import subprocess
cmd=['python','d:\\RELANGHACKATHON\\deliverables\\monocypher\\target\\main.py']
data="crypto_verify16\n45e9e59050aaac6f8b5f6429b91c815f:\n45e9e59050aaac6f8b5f6429b91c815f:\n"
r=subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=10)
print('RETURNCODE:', r.returncode)
print('STDOUT repr:', repr(r.stdout))
print('STDOUT bytes:', r.stdout.encode('utf-8'))
print('STDERR repr:', repr(r.stderr))