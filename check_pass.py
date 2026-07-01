import bcrypt

password = b"Fschp2026"
hashed = b"$2b$04$J.sBB7WA7BKnhXzxOQLG5eNo0eI4ntc/UcsjpAr9JgTDut4UB7Qym"

result = bcrypt.checkpw(password, hashed)
print("Ket qua:", result)

# In ra hash moi de dung luon
new_hash = bcrypt.hashpw(password, hashed)
print("Verify truc tiep:", bcrypt.checkpw(password, new_hash))