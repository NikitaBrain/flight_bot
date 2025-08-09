import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class FavoriteStorage:
    """Класс для работы с хранилищем избранных рейсов"""
    
    def __init__(self, storage_file='favorites.json'):
        self.file_path = Path(storage_file)
        self.data: Dict[int, List[Dict]] = {}
        self._load()
    
    def _load(self) -> None:
        """Загружает данные из файла"""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            logger.info("Favorites data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading favorites data: {e}")
            self.data = {}
    
    def _save(self) -> None:
        """Сохраняет данные в файл"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving favorites data: {e}")
    
    def get_user_favorites(self, user_id: int) -> List[Dict]:
        """Возвращает избранное пользователя"""
        return self.data.get(str(user_id), [])
    
    def add_favorite(self, user_id: int, route_data: Dict) -> bool:
        """Добавляет рейс в избранное"""
        if str(user_id) not in self.data:
            self.data[str(user_id)] = []
        
        # Проверяем на дубликаты
        if any(f['route_key'] == route_data['route_key'] for f in self.data[str(user_id)]):
            return False
        
        self.data[str(user_id)].append(route_data)
        self._save()
        return True
    
    def remove_favorite(self, user_id: int, route_key: str) -> bool:
        """Удаляет рейс из избранного"""
        if str(user_id) not in self.data:
            return False
        
        initial_length = len(self.data[str(user_id)])
        self.data[str(user_id)] = [f for f in self.data[str(user_id)] if f['route_key'] != route_key]
        
        if len(self.data[str(user_id)]) != initial_length:
            self._save()
            return True
        return False
    
    def get_all_favorites(self) -> Dict[int, List[Dict]]:
        """Возвращает все избранные рейсы всех пользователей"""
        return {int(k): v for k, v in self.data.items()}

# Глобальный экземпляр хранилища
favorite_storage = FavoriteStorage()