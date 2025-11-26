import base64
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

def encrypt_timestamp():
    # 1. 生成实时时间戳
    timestamp = str(int(time.time() * 1000))  # 13位毫秒级时间戳

    # 2. 准备加密参数
    key = "lanbu123456hndys".encode('utf-8')  # UTF-8编码密钥
    cipher = AES.new(key, AES.MODE_ECB)  # ECB模式

    # 3. 加密处理（PKCS7填充）
    padded_data = pad(timestamp.encode('utf-8'), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)

    # 4. Base64编码
    ciphertext = base64.b64encode(encrypted_bytes).decode('utf-8')

    # 5. 分割密文
    split_pos = (len(ciphertext) + 1) // 2  # 向上取整
    return {
        "custom-header": ciphertext[:split_pos],
        "bodyPart": ciphertext[split_pos:]
    }


# 使用示例
if __name__ == "__main__":

    encrypted_data = encrypt_timestamp()
    print(f"Current Timestamp: {int(time.time() * 1000)}")
    print(f"Request Header: {encrypted_data['custom-header']}")
    print(f"Request Body: {encrypted_data['bodyPart']}")
