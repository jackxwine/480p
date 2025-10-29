import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
import logging
from typing import Dict, Optional, Any, List
from bson import ObjectId
from datetime import datetime
import ssl

# Configure logging properly
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        """Connect to MongoDB with proper error handling"""
        try:
            # Get MongoDB URI from environment variable or use default
            mongodb_uri = os.getenv('MONGODB_URI', 'mongodb+srv://Wukong:MbTpYRQbVO2lUd1Z@cluster0.nlh7zf4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
            database_name = os.getenv('MONGODB_DB_NAME', 'Soloflix_Encoder')
            
            logger.info(f"Attempting to connect to MongoDB database: {database_name}")
            
            # Connection options for better stability
            self.client = MongoClient(
                mongodb_uri,
                serverSelectionTimeoutMS=10000,  # 10 second timeout
                connectTimeoutMS=30000,          # 30 second connection timeout
                socketTimeoutMS=30000,           # 30 second socket timeout
                retryWrites=True,
                ssl=True,
                ssl_cert_reqs=ssl.CERT_NONE      # For Atlas connections
            )
            
            # Test connection with timeout
            self.client.admin.command('ping')
            self.db = self.client[database_name]
            
            logger.info("✅ Connected to MongoDB successfully")
            
            # Test database access
            collections = self.db.list_collection_names()
            logger.info(f"Available collections: {collections}")
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"❌ MongoDB server selection timeout: {e}")
            self.client = None
            self.db = None
            raise
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            raise
        except OperationFailure as e:
            logger.error(f"❌ MongoDB operation failed: {e}")
            self.client = None
            self.db = None
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            self.client = None
            self.db = None
            raise

    def get_collection(self, collection_name: str):
        """Get a collection from database"""
        if self.db is None:
            raise ConnectionError("Database not connected")
        return self.db[collection_name]

    def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
            return False
        except:
            return False

class UserSettingsDB:
    def __init__(self):
        self.mongo = None
        self.collection = None
        self._is_initialized = False
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and collection"""
        try:
            self.mongo = MongoDB()
            self.collection = self.mongo.get_collection('user_settings')
            self._ensure_indexes()
            self._is_initialized = True
            logger.info("✅ UserSettingsDB initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize UserSettingsDB: {e}")
            self._is_initialized = False
            raise

    def _ensure_indexes(self):
        """Create necessary indexes for better performance"""
        try:
            self.collection.create_index("user_id", unique=True)
            self.collection.create_index("updated_at")
            logger.info("✅ Database indexes ensured")
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")

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

    def _check_connection(self):
        """Check and reestablish connection if needed"""
        if not self._is_initialized or not self.mongo or not self.mongo.is_connected():
            logger.warning("Database connection lost, reconnecting...")
            try:
                self._initialize_database()
            except Exception as e:
                logger.error(f"❌ Failed to reconnect: {e}")
                raise ConnectionError("Database connection unavailable")

    def is_ready(self) -> bool:
        """Check if database is ready to use"""
        return self._is_initialized and self.mongo and self.mongo.is_connected()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings from database"""
        self._check_connection()
        
        try:
            logger.debug(f"Fetching settings for user {user_id}")
            settings = self.collection.find_one({"user_id": user_id})
            
            if settings:
                # Remove MongoDB _id field and return
                settings_dict = dict(settings)
                settings_dict.pop('_id', None)
                logger.debug(f"Found existing settings for user {user_id}")
                return settings_dict
            else:
                # Return default settings if user doesn't exist
                logger.debug(f"No settings found for user {user_id}, returning defaults")
                return self._create_default_settings(user_id)
                
        except Exception as e:
            logger.error(f"❌ Error getting user settings for {user_id}: {e}")
            return self._create_default_settings(user_id)

    def _create_default_settings(self, user_id: int) -> Dict[str, Any]:
        """Create default settings for a user"""
        default_settings = self.DEFAULT_SETTINGS.copy()
        default_settings['user_id'] = user_id
        default_settings['created_at'] = self._get_current_timestamp()
        default_settings['updated_at'] = self._get_current_timestamp()
        return default_settings

    def update_user_settings(self, user_id: int, **kwargs) -> bool:
        """Update user settings in database"""
        try:
            self._check_connection()
        except ConnectionError:
            logger.error("❌ Cannot update settings - database connection unavailable")
            return False
        
        try:
            # Prepare update data
            update_data = {**kwargs, 'updated_at': self._get_current_timestamp()}
            
            logger.debug(f"Updating settings for user {user_id}: {update_data}")
            
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
                logger.info(f"✅ Settings updated for user {user_id}")
                return True
            logger.warning(f"⚠️ Settings update not acknowledged for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error updating settings for user {user_id}: {e}")
            return False

    def update_single_setting(self, user_id: int, setting_name: str, setting_value: Any) -> bool:
        """Update a single setting for a user"""
        return self.update_user_settings(user_id, **{setting_name: setting_value})

    def update_quality_profile(self, user_id: int, quality: str) -> bool:
        """Update user settings based on quality profile"""
        if not self.is_ready():
            logger.error("❌ Database not ready, cannot update quality profile")
            return False
            
        if quality not in self.QUALITY_PROFILES:
            logger.error(f"❌ Invalid quality profile: {quality}")
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
        
        logger.info(f"Updating quality profile to {quality} for user {user_id}")
        return self.update_user_settings(user_id, **update_data)

    def get_user_setting(self, user_id: int, setting_name: str, default: Any = None) -> Any:
        """Get a specific setting for a user"""
        settings = self.get_user_settings(user_id)
        return settings.get(setting_name, default)

    def delete_user_settings(self, user_id: int) -> bool:
        """Delete user settings from database"""
        try:
            self._check_connection()
        except ConnectionError:
            logger.error("❌ Cannot delete settings - database connection unavailable")
            return False
            
        try:
            result = self.collection.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                logger.info(f"✅ Settings deleted for user {user_id}")
                return True
            logger.warning(f"⚠️ No settings found to delete for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error deleting settings for user {user_id}: {e}")
            return False

    def get_all_users(self) -> List[int]:
        """Get all user IDs from database"""
        try:
            self._check_connection()
        except ConnectionError:
            logger.error("❌ Cannot get users - database connection unavailable")
            return []
            
        try:
            users = self.collection.find({}, {"user_id": 1})
            user_ids = [user['user_id'] for user in users]
            logger.debug(f"Found {len(user_ids)} users in database")
            return user_ids
            
        except Exception as e:
            logger.error(f"❌ Error getting all users: {e}")
            return []

    def get_users_count(self) -> int:
        """Get total number of users in database"""
        try:
            self._check_connection()
        except ConnectionError:
            logger.error("❌ Cannot get users count - database connection unavailable")
            return 0
            
        try:
            count = self.collection.count_documents({})
            logger.debug(f"Total users in database: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ Error getting users count: {e}")
            return 0

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics and settings"""
        try:
            self._check_connection()
        except ConnectionError:
            logger.error("❌ Cannot get user stats - database connection unavailable")
            return {}
            
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
                settings_dict = dict(settings)
                settings_dict.pop('_id', None)
                return settings_dict
            return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting user stats for {user_id}: {e}")
            return {}

    def _get_current_timestamp(self):
        """Get current timestamp"""
        return datetime.utcnow()

    def close_connection(self):
        """Close MongoDB connection"""
        if self.mongo and self.mongo.client:
            self.mongo.client.close()
            self._is_initialized = False
            logger.info("✅ MongoDB connection closed")

# Safe global instance with fallback
class SafeUserSettingsDB:
    """Wrapper that safely handles database operations even when connection fails"""
    
    def __init__(self):
        self._db = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database with error handling"""
        try:
            self._db = UserSettingsDB()
            logger.info("✅ UserSettingsDB instance created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create UserSettingsDB instance: {e}")
            self._db = None
    
    def __getattr__(self, name):
        """Delegate method calls to the database instance with safety checks"""
        if self._db is None:
            def method(*args, **kwargs):
                logger.error(f"❌ Database not available, cannot call {name}")
                return None
            return method
        return getattr(self._db, name)
    
    def is_ready(self) -> bool:
        """Check if database is ready"""
        return self._db is not None and self._db.is_ready()
    
    def update_quality_profile(self, user_id: int, quality: str) -> bool:
        """Safe quality profile update"""
        if not self.is_ready():
            logger.error("❌ Database not available, cannot update quality profile")
            return False
        return self._db.update_quality_profile(user_id, quality)

# Global instance with safe fallback
user_db = SafeUserSettingsDB()

# Test function to verify everything works
def test_database_connection():
    """Test the database connection and basic operations"""
    try:
        logger.info("🧪 Testing database connection...")
        
        # Initialize database
        db = UserSettingsDB()
        
        # Test user ID
        test_user_id = -1003180650405
        
        # Test getting settings
        settings = db.get_user_settings(test_user_id)
        logger.info(f"📋 User settings: {settings}")
        
        # Test updating settings
        success = db.update_user_settings(test_user_id, quality="1080p", crf="24")
        logger.info(f"📝 Update successful: {success}")
        
        # Test getting updated settings
        updated_settings = db.get_user_settings(test_user_id)
        logger.info(f"📋 Updated settings: {updated_settings}")
        
        # Test counting users
        user_count = db.get_users_count()
        logger.info(f"👥 Total users: {user_count}")
        
        db.close_connection()
        logger.info("✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

# Safe usage example
def safe_update_quality(user_id: int, quality: str):
    """Safely update quality profile with proper error handling"""
    if user_db.is_ready():
        return user_db.update_quality_profile(user_id, quality)
    else:
        logger.error("❌ Cannot update quality profile - database not available")
        return False

# Run tests if this file is executed directly
if __name__ == "__main__":
    test_database_connection()
