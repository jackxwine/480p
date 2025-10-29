import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import logging
from typing import Dict, Optional, Any, List
from bson import ObjectId

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        """Connect to MongoDB"""
        try:
            # Get MongoDB URI from environment variable or use default
            mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
            database_name = os.getenv('MONGODB_DB_NAME', 'video_encoder_bot')
            
            self.client = MongoClient(mongodb_uri)
            self.db = self.client[database_name]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("Connected to MongoDB successfully")
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def get_collection(self, collection_name: str):
        """Get a collection from database"""
        return self.db[collection_name]

class UserSettingsDB:
    def __init__(self):
        self.mongo = MongoDB()
        self.collection = self.mongo.get_collection('user_settings')
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for better performance"""
        try:
            self.collection.create_index("user_id", unique=True)
            self.collection.create_index("updated_at")
            logger.info("Database indexes ensured")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    # Default settings
    DEFAULT_SETTINGS = {
        'crf': '28',
        'codec': 'libx264',
        'resolution': '1280x720',
        'preset': 'veryfast',
        'audio_b': '40k',
        'quality': '720p',
        'custom_settings': {}
    }

    # Quality profiles
    QUALITY_PROFILES = {
        "360p": {"resolution": "640x360", "crf": "30", "audio": "64k"},
        "480p": {"resolution": "854x480", "crf": "28", "audio": "96k"},
        "720p": {"resolution": "1280x720", "crf": "26", "audio": "128k"},
        "1080p": {"resolution": "1920x1080", "crf": "24", "audio": "192k"},
        "original": {"resolution": "original", "crf": "28", "audio": "40k"}
    }

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings from database"""
        try:
            settings = self.collection.find_one({"user_id": user_id})
            
            if settings:
                # Remove MongoDB _id field and return
                settings.pop('_id', None)
                return settings
            else:
                # Return default settings if user doesn't exist
                return self._create_default_settings(user_id)
                
        except Exception as e:
            logger.error(f"Error getting user settings for {user_id}: {e}")
            return self._create_default_settings(user_id)

    def _create_default_settings(self, user_id: int) -> Dict[str, Any]:
        """Create default settings for a user"""
        default_settings = self.DEFAULT_SETTINGS.copy()
        default_settings['user_id'] = user_id
        return default_settings

    def update_user_settings(self, user_id: int, **kwargs) -> bool:
        """Update user settings in database"""
        try:
            # Prepare update data
            update_data = {**kwargs, 'updated_at': self._get_current_timestamp()}
            
            result = self.collection.update_one(
                {"user_id": user_id},
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        "user_id": user_id,
                        "created_at": self._get_current_timestamp()
                    }
                },
                upsert=True
            )
            
            if result.acknowledged:
                logger.info(f"Settings updated for user {user_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating settings for user {user_id}: {e}")
            return False

    def update_single_setting(self, user_id: int, setting_name: str, setting_value: Any) -> bool:
        """Update a single setting for a user"""
        return self.update_user_settings(user_id, **{setting_name: setting_value})

    def update_quality_profile(self, user_id: int, quality: str) -> bool:
        """Update user settings based on quality profile"""
        if quality not in self.QUALITY_PROFILES:
            return False
            
        profile = self.QUALITY_PROFILES[quality]
        update_data = {
            'quality': quality,
            'crf': profile['crf'],
            'audio_b': profile['audio']
        }
        
        # Only update resolution if not "original"
        if profile['resolution'] != 'original':
            update_data['resolution'] = profile['resolution']
        
        return self.update_user_settings(user_id, **update_data)

    def get_user_setting(self, user_id: int, setting_name: str, default: Any = None) -> Any:
        """Get a specific setting for a user"""
        settings = self.get_user_settings(user_id)
        return settings.get(setting_name, default)

    def delete_user_settings(self, user_id: int) -> bool:
        """Delete user settings from database"""
        try:
            result = self.collection.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                logger.info(f"Settings deleted for user {user_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting settings for user {user_id}: {e}")
            return False

    def get_all_users(self) -> List[int]:
        """Get all user IDs from database"""
        try:
            users = self.collection.find({}, {"user_id": 1})
            return [user['user_id'] for user in users]
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    def get_users_count(self) -> int:
        """Get total number of users in database"""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"Error getting users count: {e}")
            return 0

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics and settings"""
        try:
            settings = self.collection.find_one(
                {"user_id": user_id},
                {
                    "user_id": 1,
                    "quality": 1,
                    "crf": 1,
                    "resolution": 1,
                    "codec": 1,
                    "preset": 1,
                    "audio_b": 1,
                    "created_at": 1,
                    "updated_at": 1
                }
            )
            
            if settings:
                settings.pop('_id', None)
                return settings
            return {}
            
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return {}

    def _get_current_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow()

    def close_connection(self):
        """Close MongoDB connection"""
        if self.mongo.client:
            self.mongo.client.close()
            logger.info("MongoDB connection closed")

# Global instance
user_db = UserSettingsDB()
