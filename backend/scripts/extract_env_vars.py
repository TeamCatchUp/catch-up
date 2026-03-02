import re

dotenv_file = "../../.env"
dotenv_file_var_only = "../../.env.var"

var_pattern = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=")

var_list = []

with open(dotenv_file, "r", encoding="utf-8") as f:
    for line in f:
        match = var_pattern.match(line)
        if match:
            var_list.append(match.group(1))

with open(dotenv_file_var_only, "w", encoding="utf-8") as v:
    v.write("\n".join(var_list) + "\n")

print(f"Extracted {len(var_list)} vars from .env")