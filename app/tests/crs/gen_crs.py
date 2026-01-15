import csv
import secrets
import string
from pathlib import Path

from pwdlib import PasswordHash

BASE_DIR = Path(__file__).resolve().parent

INPUT = BASE_DIR / "crs_seed.csv"
OUT_IMPORT = BASE_DIR / "crs_import.csv"
OUT_ADMIN = BASE_DIR / "crs_passwords.csv"

password_hash = PasswordHash.recommended()  # argon2id


def gen_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    for c in "0OoIl":
        chars = chars.replace(c, "")
    return "".join(secrets.choice(chars) for _ in range(length))


def hash_password(plain: str) -> str:
    return password_hash.hash(plain)


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing file: {INPUT}")

    import_rows = []
    admin_rows = []

    with INPUT.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {"roll_no", "neura_cr_id"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("crs_seed.csv must have: roll_no, neura_cr_id")

        for r in reader:
            roll_no = (r.get("roll_no") or "").strip()
            neura_cr_id = (r.get("neura_cr_id") or "").strip()

            if not roll_no or not neura_cr_id:
                continue

            plain = gen_password()
            hashed = hash_password(plain)

            import_rows.append(
                {
                    "roll_no": roll_no,
                    "neura_cr_id": neura_cr_id,
                    "password": hashed,
                }
            )

            admin_rows.append(
                {
                    "roll_no": roll_no,
                    "neura_cr_id": neura_cr_id,
                    "password": plain,
                }
            )

    with OUT_IMPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["roll_no", "neura_cr_id", "password"])
        w.writeheader()
        w.writerows(import_rows)

    with OUT_ADMIN.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["roll_no", "neura_cr_id", "password"])
        w.writeheader()
        w.writerows(admin_rows)

    print("Upload to Supabase:", OUT_IMPORT)
    print("Distribute to users:", OUT_ADMIN)
    print("Rows created:", len(import_rows))


if __name__ == "__main__":
    main()
