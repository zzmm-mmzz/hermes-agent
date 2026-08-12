"""验证密码 MD5"""
import hashlib

pwd = "hejie.1161"
print(f"md5('{pwd}') = {hashlib.md5(pwd.encode('utf-8')).hexdigest()}")

# 也可能是 GBK 编码
try:
    print(f"md5(GBK) = {hashlib.md5(pwd.encode('gbk')).hexdigest()}")
except:
    pass

# 是否密码有特殊字符？
print(f"Password length: {len(pwd)}")
print(f"Password bytes: {list(pwd.encode('utf-8'))}")
print()

# 验证前端 encrypt 函数中的 password 处理
# aostaritEncryptUtils.string.encrypt(userPwd, true)
# force=true, smPass=false (isIE8=true)
# 所以走 IE8 分支:
#   key = encryptKey.split('#')
#   key_pair = RSAUtils.getKeyPair(keys[1], '', keys[0])
#   envelope = $.md5(str) + random + str
#   encrypted = RSAUtils.encryptedString(key_pair, envelope)
# random=getRandomString(8)
# 其中 getRandomString = function(len) { return ... } 
# 需要确认 random 的字符集

# 检查前端 getRandomString 函数
print("getRandomString 在 encrypt.js 中可能需要确认")
