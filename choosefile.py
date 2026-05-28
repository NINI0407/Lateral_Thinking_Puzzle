import os  # 處理檔案與資料夾相關操作
import random  # 用來從多個 txt 中隨機選一個

# 指定資料夾路徑（請自行修改為實際資料夾路徑）
folder_path = "C:/Users/YourName/Documents/txt_folder"

# 取得資料夾中所有檔案名稱
all_files = os.listdir(folder_path)

# 過濾出所有 .txt 檔案
txt_files = [f for f in all_files if f.endswith('.txt')]

# 檢查是否有找到 txt 檔案
if not txt_files:
    print("資料夾中沒有 .txt 檔案")
else:
    # 隨機選取一個 txt 檔案（你也可以用 txt_files[0] 取第一個）
    chosen_file = random.choice(txt_files)
    #建立txt路徑
    full_path = os.path.join(folder_path, chosen_file)

    # 打開並讀取檔案內容
    with open(full_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 印出檔案名稱與內容
    print(f"讀取檔案：{chosen_file}")
    print("內容如下：")
    print(content)
