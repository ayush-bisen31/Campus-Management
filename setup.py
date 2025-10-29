import os

# Step 1: Create .streamlit folder
if not os.path.exists('.streamlit'):
    os.makedirs('.streamlit')
    print("✅ Created .streamlit folder")
else:
    print("✅ .streamlit folder already exists")

# Step 2: Ask for password
print("\n" + "="*50)
print("Enter your Google Cloud SQL root password:")
password = input("Password: ")

# Step 3: Create secrets.toml
secrets_content = f"""[database]
host = "35.193.198.62"
user = "root"
password = "{AyNi@9689}"
database = "Campus_management"
port = 3306
"""

# Step 4: Write to file
secrets_path = os.path.join('.streamlit', 'secrets.toml')
with open(secrets_path, 'w') as f:
    f.write(secrets_content)

print(f"\n✅ SUCCESS! File created at: {secrets_path}")
print("\nContents:")
print("="*50)
print(secrets_content)
print("="*50)

# Step 5: Verify
if os.path.exists(secrets_path):
    print("\n✅ File verified successfully!")
    print(f"📁 Full path: {os.path.abspath(secrets_path)}")
else:
    print("\n❌ Something went wrong!")