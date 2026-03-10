from pathlib import Path

env_example = Path(".env.example")
output = Path("app/version.py")

version = "dev"

if env_example.exists():
    for line in env_example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("APP_VERSION="):
            version = line.split("=", 1)[1].strip()
            break

output.write_text(f'VERSION = "{version}"\n', encoding="utf-8")
print(f"Generated app/version.py with VERSION={version}")