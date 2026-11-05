import os
import subprocess
from pathlib import Path

cwd = os.getcwd()
print(f"Before {cwd}")
os.chdir(Path(__file__).parent)

REMOVE = f"sudo rm -rf {Path('~/.docker-conf/postgresql_data/').expanduser()}".split()
DOWN = "docker compose down".split()
UP = "docker compose up -d".split()

print("Down")
subprocess.call(DOWN)
print("Remove")
subprocess.call(REMOVE)
print("Up")
subprocess.call(UP)
print("Done")

os.chdir(cwd)
