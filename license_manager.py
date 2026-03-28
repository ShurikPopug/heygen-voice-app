"""
Модуль управления лицензией HeyGen Voice Generator
"""

import json
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
import platform
import subprocess
import uuid
import os
import sys
import random
import string

class LicenseManager:
    def __init__(self):
        def get_app_data_dir():
            """Возвращает надежную папку для хранения данных приложения"""
            if sys.platform == "darwin":
                path = os.path.expanduser("~/Library/Application Support/HeyGenVoice")
            elif os.name == "nt":
                path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "HeyGenVoice")
            else:
                path = os.path.expanduser("~/.heygen_voice")

            os.makedirs(path, exist_ok=True)
            return path

        self.current_dir = get_app_data_dir()

        self.license_file = os.path.join(self.current_dir, "license.lic")
        self.salt_file = os.path.join(self.current_dir, ".machine_salt")
        self.verification_key = self._get_verification_key()

        self._migrate_old_files()

    def _migrate_old_files(self):
        """Переносит старые файлы лицензии из папки приложения"""
        try:
            if getattr(sys, 'frozen', False):
                old_dir = os.path.dirname(sys.executable)
            else:
                old_dir = os.path.dirname(os.path.abspath(__file__))

            old_license = os.path.join(old_dir, "license.lic")
            old_salt = os.path.join(old_dir, ".machine_salt")

            if os.path.exists(old_license) and not os.path.exists(self.license_file):
                import shutil
                shutil.copy2(old_license, self.license_file)

            if os.path.exists(old_salt) and not os.path.exists(self.salt_file):
                import shutil
                shutil.copy2(old_salt, self.salt_file)

        except Exception as e:
            print(f"Migration error: {e}")
    
    def _get_verification_key(self):
        """Возвращает ключ для проверки подписи"""
        return b"HeyGen_Voice_Secret_Key_2024_Do_Not_Share!"

    def _get_or_create_salt(self):
        if os.path.exists(self.salt_file):
            try:
                with open(self.salt_file, 'r', encoding='utf-8') as f:
                    salt = f.read().strip()
                if salt:
                    return salt
            except Exception as e:
                raise RuntimeError(f"Ошибка чтения соли: {e}")

        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        temp_file = self.salt_file + ".tmp"

        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(salt)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_file, self.salt_file)

            with open(self.salt_file, 'r', encoding='utf-8') as f:
                saved = f.read().strip()

            if saved != salt:
                raise RuntimeError("Соль записана некорректно")

            return saved

        except Exception as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

            raise RuntimeError(f"Не удалось сохранить machine_salt: {e}")
    
    def get_machine_id(self):
        """Получает уникальный ID компьютера"""
        # Собираем информацию о системе
        system_info = []
        
        # 1. Имя компьютера
        system_info.append(platform.node())
        
        # 2. Операционная система
        system_info.append(platform.system())
        
        # 3. Архитектура
        system_info.append(platform.machine())
        
        # 4. Процессор
        system_info.append(platform.processor())
        
        # 5. MAC-адрес
        try:
            mac = uuid.getnode()
            system_info.append(str(mac))
        except:
            system_info.append("no_mac")
        
        # 6. Серийный номер диска (Windows)
        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                volume_serial = ctypes.c_uint32()
                kernel32.GetVolumeInformationW(
                    "C:\\", None, 0, ctypes.byref(volume_serial), None, None, None, 0
                )
                system_info.append(str(volume_serial.value))
            except:
                system_info.append("no_volume")
        
        # 7. Machine ID для Linux
        if platform.system() == "Linux":
            try:
                with open('/etc/machine-id', 'r') as f:
                    system_info.append(f.read().strip())
            except:
                system_info.append("no_machine_id")
        
        # 8. Серийный номер для macOS
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'], 
                    capture_output=True, 
                    text=True,
                    timeout=5
                )
                import re
                serial_match = re.search(r'Serial Number \(system\): (.+)', result.stdout)
                if serial_match:
                    system_info.append(serial_match.group(1).strip())
                else:
                    system_info.append("no_serial")
            except:
                system_info.append("no_serial")
        
        # 9. Соль (постоянная, из файла)
        salt = self._get_or_create_salt()
        system_info.append(salt)
        
        # Объединяем всё и хешируем
        combined = "|".join(system_info)
        machine_id = hashlib.sha256(combined.encode()).hexdigest()
        
        return machine_id
    
    def verify_license_key(self, license_key):
        """
        Проверяет лицензионный ключ и активирует лицензию
        
        Returns:
            tuple: (success, message)
        """
        try:
            # Декодируем ключ
            license_data = base64.b64decode(license_key).decode()
            machine_id_from_key, expiry_date, signature = license_data.split(':')
            
            # Получаем ID текущего компьютера
            current_machine_id = self.get_machine_id()
            
            # 1. Проверяем привязку к компьютеру
            if machine_id_from_key != current_machine_id:
                return False, "Ключ предназначен для другого компьютера"
            
            # 2. Проверяем подпись
            message = f"{machine_id_from_key}:{expiry_date}".encode()
            expected_signature = hmac.new(
                self.verification_key, 
                message, 
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, signature):
                return False, "Неверная подпись ключа"
            
            # 3. Проверяем срок действия
            expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
            if datetime.now() > expiry:
                return False, f"Срок действия истек ({expiry_date})"
            
            # Всё хорошо - сохраняем лицензию
            license_info = {
                "machine_id": machine_id_from_key,
                "expiry_date": expiry_date,
                "signature": signature,
                "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.license_file, 'w') as f:
                json.dump(license_info, f, indent=2)
            
            return True, "Лицензия активирована успешно!"
            
        except Exception as e:
            return False, f"Ошибка проверки ключа: {str(e)}"
    
    def check_license(self):
        """Проверяет существующую лицензию"""
        if not os.path.exists(self.license_file):
            return False
        
        try:
            with open(self.license_file, 'r') as f:
                license_info = json.load(f)
            
            # Проверяем привязку к компьютеру
            current_machine_id = self.get_machine_id()
            if license_info['machine_id'] != current_machine_id:
                return False
            
            # Проверяем подпись
            message = f"{license_info['machine_id']}:{license_info['expiry_date']}".encode()
            expected_signature = hmac.new(
                self.verification_key, 
                message, 
                hashlib.sha256
            ).hexdigest()
            
            if license_info['signature'] != expected_signature:
                return False
            
            # Проверяем срок действия
            expiry_date = datetime.strptime(license_info['expiry_date'], "%Y-%m-%d")
            if datetime.now() > expiry_date:
                return False
            
            return True
            
        except Exception as e:
            print(f"Ошибка проверки лицензии: {e}")
            return False
    
    def get_license_info(self):
        """Возвращает информацию о лицензии"""
        if not os.path.exists(self.license_file):
            return None
        
        try:
            with open(self.license_file, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def is_license_valid(self, license_info):
        """
        Проверяет, не истекла ли лицензия
        
        Args:
            license_info (dict): Словарь с информацией о лицензии
            
        Returns:
            bool: True если лицензия действительна, False если истекла
        """
        try:
            expiry_date = datetime.strptime(license_info['expiry_date'], "%Y-%m-%d")
            return datetime.now() <= expiry_date
        except:
            return False