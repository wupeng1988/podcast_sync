import os
import time
from aligo import Aligo

class AliyunClient:
    def __init__(self, refresh_token="", token_file=""):
        kwargs = {}
        if refresh_token:
            kwargs["refresh_token"] = refresh_token
        if token_file:
            kwargs["name"] = token_file
        self.ali = Aligo(**kwargs)
        self._dir_cache = {}

    def _get_or_create_folder(self, folder_path):
        """获取或创建目录，返回 folder_id"""
        if folder_path in self._dir_cache:
            return self._dir_cache[folder_path]

        # 从根目录开始逐级查找/创建
        parts = [p for p in folder_path.split("/") if p]
        parent_id = "root"

        for part in parts:
            # 尝试获取
            folder = self.ali.get_folder_by_path(
                folder_path, parent_file_id=parent_id
            ) if False else None

            # 简化：用 get_file_list 逐级找
            folder = None
            try:
                file_list = self.ali.get_file_list(parent_file_id=parent_id)
                for f in file_list:
                    if f.name == part and f.type == "folder":
                        folder = f
                        break
            except Exception:
                pass

            if folder is None:
                folder = self.ali.create_folder(name=part, parent_file_id=parent_id)
                time.sleep(1)  # 避免触发频率限制

            parent_id = folder.file_id

        self._dir_cache[folder_path] = parent_id
        return parent_id

    def upload_file(self, local_path, aliyun_dir, file_name, overwrite=True):
        """
        上传文件到阿里云盘指定目录。
        overwrite=True 时，同名文件先删除再上传。
        返回 (成功?, 错误信息, file_id)
        """
        try:
            parent_id = self._get_or_create_folder(aliyun_dir)

            # 检查同名文件
            if overwrite:
                try:
                    file_list = self.ali.get_file_list(parent_file_id=parent_id)
                    for f in file_list:
                        if f.name == file_name:
                            self.ali.delete_file(file_id=f.file_id)
                            time.sleep(1)
                            break
                except Exception:
                    pass  # 列表获取失败时，直接尝试上传

            uploaded = self.ali.upload_file(
                file_path=local_path,
                parent_file_id=parent_id,
                name=file_name,
            )
            return True, "", uploaded.file_id

        except Exception as e:
            err = str(e)
            # 检测 429 限流
            if "429" in err or "Too Many Requests" in err:
                return False, f"RATE_LIMIT: {err}", None
            return False, err, None
