import requests

# 下载图片到tmp文件夹

def download_file(url, local_filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

if __name__ == "__main__":
    url = "https://gchat.qpic.cn/qmeetpic/673753304020408412/655932294-2819915668-10C3A477751E679CE9B5E2A71B140C16/0"
    download_file(url, "tmp/1.jpg")