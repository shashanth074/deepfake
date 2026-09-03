import os
import zipfile

def zip_project(src_dir, zip_name):
    exclude_dirs = {'.venv', 'node_modules', '.git', '__pycache__', 'data', 'storage', '.vscode'}
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(src_dir):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, src_dir)
                zipf.write(file_path, arcname)

if __name__ == '__main__':
    src = r"c:\Users\admin\Desktop\New folder (3)\FORENSICS"
    dst = r"c:\Users\admin\Desktop\New folder (3)\FORENSICS.zip"
    zip_project(src, dst)
    print("Zip created successfully!")
