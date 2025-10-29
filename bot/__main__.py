from datetime import datetime as dt
import os, asyncio, pyrogram, psutil, platform, time
from bot import (
    APP_ID,
    API_HASH,
    AUTH_USERS,
    DOWNLOAD_LOCATION,
    LOGGER,
    TG_BOT_TOKEN,
    BOT_USERNAME,
    SESSION_NAME,
    
    data,
    app,
    crf,
    resolution,
    audio_b,
    preset,
    codec,
    watermark 
)
from bot.helper_funcs.utils import add_task, on_task_complete, sysinfo
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import Message
from psutil import disk_usage, cpu_percent, virtual_memory, Process as psprocess
from bot.database import user_db  # Import MongoDB database
import logging

logger = logging.getLogger(__name__)

from bot.plugins.incoming_message_fn import (
    incoming_start_message_f,
    incoming_compress_message_f,
    incoming_cancel_message_f
)

# 🤣
uptime = dt.now()

def ts(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "")
        + ((str(hours) + "h, ") if hours else "")
        + ((str(minutes) + "m, ") if minutes else "")
        + ((str(seconds) + "s, ") if seconds else "")
        + ((str(milliseconds) + "ms, ") if milliseconds else "")
    )
    return tmp[:-2]

def get_user_settings(user_id: int):
    """Get user settings from database with fallback"""
    try:
        if user_db is None or not user_db.is_ready():
            logger.error("Database not initialized")
            return user_db._create_default_settings(user_id)
        return user_db.get_user_settings(user_id)
    except Exception as e:
        logger.error(f"Error getting user settings for {user_id}: {e}")
        return user_db._create_default_settings(user_id)

def update_user_settings(user_id: int, **kwargs):
    """Update user settings in database with error handling"""
    try:
        if user_db is None or not user_db.is_ready():
            logger.error("Database not initialized")
            return False
        return user_db.update_user_settings(user_id, **kwargs)
    except Exception as e:
        logger.error(f"Error updating settings for {user_id}: {e}")
        return False

def get_encoding_settings(user_id: int):
    """Get encoding settings for a user with fallback to defaults"""
    try:
        settings = get_user_settings(user_id)
        
        # Ensure all required settings are present
        encoding_settings = {
            'crf': settings.get('crf', '28'),
            'codec': settings.get('codec', 'libx264'),
            'resolution': settings.get('resolution', '1280x720'),
            'preset': settings.get('preset', 'veryfast'),
            'audio_b': settings.get('audio_b', '40k'),
            'quality': settings.get('quality', '720p'),
            'user_id': user_id  # Track which user's settings are being used
        }
        
        return encoding_settings
    except Exception as e:
        logger.error(f"Error getting encoding settings for {user_id}: {e}")
        # Return hardcoded defaults as fallback
        return {
            'crf': '28',
            'codec': 'libx264',
            'resolution': '1280x720',
            'preset': 'veryfast',
            'audio_b': '40k',
            'quality': '720p',
            'user_id': user_id
        }

def safe_update_quality(user_id: int, quality: str) -> bool:
    """Safely update quality profile with proper error handling"""
    try:
        if user_db is None or not user_db.is_ready():
            logger.error("Database not available for quality update")
            return False
        return user_db.update_quality_profile(user_id, quality)
    except Exception as e:
        logger.error(f"Error updating quality for {user_id}: {e}")
        return False

def log_encoding_activity(user_id: int, file_info: dict, settings_used: dict, status: str):
    """Log encoding activity to database"""
    try:
        if user_db.is_ready():
            # Create activity log entry
            activity_data = {
                'user_id': user_id,
                'timestamp': dt.utcnow(),
                'activity_type': 'encoding',
                'status': status,
                'file_info': file_info,
                'settings_used': settings_used
            }
            
            # Store in a separate collection for activity logs
            activity_collection = user_db.mongo.get_collection('encoding_activities')
            activity_collection.insert_one(activity_data)
            logger.debug(f"Activity logged for user {user_id}")
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def get_user_encoding_stats(user_id: int) -> dict:
    """Get user encoding statistics"""
    try:
        if user_db.is_ready():
            activity_collection = user_db.mongo.get_collection('encoding_activities')
            
            # Count total encodings
            total_encodings = activity_collection.count_documents({
                'user_id': user_id, 
                'activity_type': 'encoding'
            })
            
            # Count successful encodings
            successful_encodings = activity_collection.count_documents({
                'user_id': user_id, 
                'activity_type': 'encoding',
                'status': 'completed'
            })
            
            # Get last encoding time
            last_encoding = activity_collection.find_one({
                'user_id': user_id,
                'activity_type': 'encoding'
            }, sort=[('timestamp', -1)])
            
            return {
                'total_encodings': total_encodings,
                'successful_encodings': successful_encodings,
                'last_encoding_time': last_encoding.get('timestamp') if last_encoding else None
            }
    except Exception as e:
        logger.error(f"Error getting user encoding stats: {e}")
    
    return {'total_encodings': 0, 'successful_encodings': 0, 'last_encoding_time': None}

if __name__ == "__main__" :
    # create download directory, if not exist
    if not os.path.isdir(DOWNLOAD_LOCATION):
        os.makedirs(DOWNLOAD_LOCATION)
    
    # Initialize database connection
    try:
        if user_db is None or not user_db.is_ready():
            logger.error("❌ Database connection failed - using default settings")
        else:
            logger.info("✅ Database connection established successfully")
            
            # Log bot startup in database
            if user_db.is_ready():
                activity_collection = user_db.mongo.get_collection('bot_activities')
                activity_collection.insert_one({
                    'event': 'bot_startup',
                    'timestamp': dt.utcnow(),
                    'uptime': uptime,
                    'total_users': user_db.get_users_count()
                })
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")

    # STATUS ADMIN Command

    # START command
    incoming_start_message_handler = MessageHandler(
        incoming_start_message_f,
        filters=filters.command(["start", f"start@{BOT_USERNAME}"])
    )
    app.add_handler(incoming_start_message_handler)
    
    @app.on_message(filters.incoming & filters.command(["crf", f"crf@{BOT_USERNAME}"]))
    async def changecrf(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            current_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Current CRF:</b> <code>{current_settings.get('crf', '28')}</code>\n\n"
                f"<b>Usage:</b> <code>/crf 24</code>\n"
                f"<b>Recommended:</b> 18-28 (lower = better quality, larger file)"
            )
            
        cr = message.text.split(" ", maxsplit=1)[1]
        OUT = f"<blockquote>✅ CRF updated to: {cr}</blockquote>"
        
        # Update in database
        success = update_user_settings(message.chat.id, crf=cr)
        if not success:
            OUT = "<blockquote>❌ Failed to update CRF</blockquote>"
        else:
            # Log setting change
            log_encoding_activity(
                message.chat.id,
                {'action': 'setting_change', 'setting': 'crf', 'value': cr},
                get_user_settings(message.chat.id),
                'setting_updated'
            )
            
        await message.reply_text(OUT)

    @app.on_message(filters.incoming & filters.command(["resolution", f"resolution@{BOT_USERNAME}"]))
    async def changer(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            current_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Current Resolution:</b> <code>{current_settings.get('resolution', '1280x720')}</code>\n\n"
                f"<b>Usage:</b> <code>/resolution 1920x1080</code>\n"
                f"<b>Examples:</b> 640x360, 854x480, 1280x720, 1920x1080"
            )
            
        r = message.text.split(" ", maxsplit=1)[1]
        OUT = f"<blockquote>✅ Resolution updated to: {r}</blockquote>"
        
        # Update in database
        success = update_user_settings(message.chat.id, resolution=r)
        if not success:
            OUT = "<blockquote>❌ Failed to update resolution</blockquote>"
        else:
            # Log setting change
            log_encoding_activity(
                message.chat.id,
                {'action': 'setting_change', 'setting': 'resolution', 'value': r},
                get_user_settings(message.chat.id),
                'setting_updated'
            )
            
        await message.reply_text(OUT)

    @app.on_message(filters.incoming & filters.command(["preset", f"preset@{BOT_USERNAME}"]))
    async def changepr(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            current_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Current Preset:</b> <code>{current_settings.get('preset', 'veryfast')}</code>\n\n"
                f"<b>Usage:</b> <code>/preset veryfast</code>\n"
                f"<b>Options:</b> ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow"
            )
            
        pop = message.text.split(" ", maxsplit=1)[1]
        OUT = f"<blockquote>✅ Preset updated to: {pop}</blockquote>"
        
        # Update in database
        success = update_user_settings(message.chat.id, preset=pop)
        if not success:
            OUT = "<blockquote>❌ Failed to update preset</blockquote>"
        else:
            # Log setting change
            log_encoding_activity(
                message.chat.id,
                {'action': 'setting_change', 'setting': 'preset', 'value': pop},
                get_user_settings(message.chat.id),
                'setting_updated'
            )
            
        await message.reply_text(OUT)

    @app.on_message(filters.incoming & filters.command(["codec", f"codec@{BOT_USERNAME}"]))
    async def changecode(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            current_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Current Codec:</b> <code>{current_settings.get('codec', 'libx264')}</code>\n\n"
                f"<b>Usage:</b> <code>/codec libx264</code>\n"
                f"<b>Options:</b> libx264, libx265, libvpx-vp9"
            )
            
        col = message.text.split(" ", maxsplit=1)[1]
        OUT = f"<blockquote>✅ Codec updated to: {col}</blockquote>"
        
        # Update in database
        success = update_user_settings(message.chat.id, codec=col)
        if not success:
            OUT = "<blockquote>❌ Failed to update codec</blockquote>"
        else:
            # Log setting change
            log_encoding_activity(
                message.chat.id,
                {'action': 'setting_change', 'setting': 'codec', 'value': col},
                get_user_settings(message.chat.id),
                'setting_updated'
            )
            
        await message.reply_text(OUT)

    @app.on_message(filters.incoming & filters.command(["audio", f"audio@{BOT_USERNAME}"]))
    async def changea(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            current_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Current Audio Bitrate:</b> <code>{current_settings.get('audio_b', '40k')}</code>\n\n"
                f"<b>Usage:</b> <code>/audio 128k</code>\n"
                f"<b>Examples:</b> 64k, 96k, 128k, 192k, 256k"
            )
            
        aud = message.text.split(" ", maxsplit=1)[1]
        OUT = f"<blockquote>✅ Audio bitrate updated to: {aud}</blockquote>"
        
        # Update in database
        success = update_user_settings(message.chat.id, audio_b=aud)
        if not success:
            OUT = "<blockquote>❌ Failed to update audio bitrate</blockquote>"
        else:
            # Log setting change
            log_encoding_activity(
                message.chat.id,
                {'action': 'setting_change', 'setting': 'audio_b', 'value': aud},
                get_user_settings(message.chat.id),
                'setting_updated'
            )
            
        await message.reply_text(OUT)
    
    # Multi-quality command handler
    @app.on_message(filters.incoming & filters.command(["quality", f"quality@{BOT_USERNAME}"]))
    async def change_quality(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        if len(message.command) < 2:
            qualities = "\n".join([f"• {quality}" for quality in user_db.QUALITY_PROFILES.keys()])
            user_settings = get_user_settings(message.chat.id)
            return await message.reply_text(
                f"<b>Available Quality Profiles:</b>\n<blockquote>{qualities}</blockquote>\n"
                f"<b>Current Quality:</b> <code>{user_settings.get('quality', '720p')}</code>\n\n"
                f"<b>Usage:</b> <code>/quality 720p</code>"
            )
        
        quality = message.command[1].lower()
        if quality in user_db.QUALITY_PROFILES:
            # Update quality in database
            success = safe_update_quality(message.chat.id, quality)
            if success:
                profile = user_db.QUALITY_PROFILES[quality]
                quality_info = (
                    f"<b>Quality changed to:</b> <code>{quality.upper()}</code>\n\n"
                    f"<b>Settings Applied:</b>\n"
                    f"• <b>Resolution:</b> <code>{profile['resolution']}</code>\n"
                    f"• <b>CRF:</b> <code>{profile['crf']}</code>\n"
                    f"• <b>Audio:</b> <code>{profile['audio']}</code>"
                )
                
                # Log quality change
                log_encoding_activity(
                    message.chat.id,
                    {'action': 'quality_change', 'quality': quality, 'profile': profile},
                    get_user_settings(message.chat.id),
                    'quality_updated'
                )
                
                await message.reply_text(quality_info)
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality settings</blockquote>")
        else:
            await message.reply_text(
                "<b>Invalid quality profile!</b>\n\n"
                "<b>Available options:</b> <code>360p, 480p, 720p, 1080p, original</code>"
            )
    
    # Quick quality commands
    @app.on_message(filters.incoming & filters.command(["360p", f"360p@{BOT_USERNAME}"]))
    async def set_360p(app, message):
        if message.chat.id in AUTH_USERS:
            success = safe_update_quality(message.chat.id, "360p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 360p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["480p", f"480p@{BOT_USERNAME}"]))
    async def set_480p(app, message):
        if message.chat.id in AUTH_USERS:
            success = safe_update_quality(message.chat.id, "480p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 480p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["720p", f"720p@{BOT_USERNAME}"]))
    async def set_720p(app, message):
        if message.chat.id in AUTH_USERS:
            success = safe_update_quality(message.chat.id, "720p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 720p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["1080p", f"1080p@{BOT_USERNAME}"]))
    async def set_1080p(app, message):
        if message.chat.id in AUTH_USERS:
            success = safe_update_quality(message.chat.id, "1080p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 1080p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["original", f"original@{BOT_USERNAME}"]))
    async def set_original(app, message):
        if message.chat.id in AUTH_USERS:
            success = safe_update_quality(message.chat.id, "original")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to Original (No resolution change)</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")

    @app.on_message(filters.incoming & filters.command(["compress", f"compress@{BOT_USERNAME}"]))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote> Aᴅᴍɪɴ Oɴʟʏ 🔒 </blockquote>")
        
        # Get user settings for encoding
        user_settings = get_encoding_settings(message.chat.id)
        
        query = await message.reply_text("Aᴅᴅᴇᴅ Tᴏ Qᴜᴇᴜᴇ ⏰...\nPʟᴇᴀꜱᴇ ʙᴇ Pᴀᴛɪᴇɴᴛ, Cᴏᴍᴘʀᴇꜱꜱ ᴡɪʟʟ Sᴛᴀʀᴛ Sᴏᴏɴ", quote=True)
        data.append(message.reply_to_message)
        if len(data) == 1:
            await query.delete()   
            
            # Log encoding start
            file_info = {
                'file_id': message.reply_to_message.id,
                'file_type': 'video' if message.reply_to_message.video else 'document',
                'timestamp': dt.utcnow()
            }
            log_encoding_activity(
                message.chat.id,
                file_info,
                user_settings,
                'encoding_started'
            )
            
            await add_task(message.reply_to_message, user_settings)     
 
    @app.on_message(filters.incoming & filters.command(["restart", f"restart@{BOT_USERNAME}"]))
    async def restarter(app, message):
        if message.chat.id in AUTH_USERS:
            # Log restart event
            if user_db.is_ready():
                activity_collection = user_db.mongo.get_collection('bot_activities')
                activity_collection.insert_one({
                    'event': 'bot_restart',
                    'timestamp': dt.utcnow(),
                    'initiated_by': message.chat.id
                })
            await message.reply_text("Rᴇꜱᴛᴀʀᴛɪɴɢ...♻️")
            quit(1)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
            
    @app.on_message(filters.incoming & filters.command(["clear", f"clear@{BOT_USERNAME}"]))
    async def restarter(app, message):
        data.clear()
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪꜱᴇᴅ Tᴏ Uꜱᴇ Tʜɪꜱ Bᴏᴛ Cᴏɴᴛᴀᴄᴛ @Lord_Vasudev_Krishna</blockquote>")
        
        # Log queue clear
        if user_db.is_ready():
            activity_collection = user_db.mongo.get_collection('bot_activities')
            activity_collection.insert_one({
                'event': 'queue_cleared',
                'timestamp': dt.utcnow(),
                'cleared_by': message.chat.id,
                'queue_size_before': len(data)
            })
            
        query = await message.reply_text("<blockquote>Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʟᴇᴀʀᴇᴅ Qᴜᴇᴜᴇ...📚</blockquote>")
      
        
    @app.on_message(filters.incoming & (filters.video | filters.document))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪꜱᴇᴅ Tᴏ Uꜱᴇ Tʜɪꜱ Bᴏᴛ Cᴏɴᴛᴀᴄᴛ @Itz_Sizian</blockquote>")
        
        # Get user settings for encoding
        user_settings = get_encoding_settings(message.chat.id)
        
        query = await message.reply_text("Aᴅᴅᴇᴅ Tᴏ Qᴜᴇᴜᴇ ⏰...\nPʟᴇᴀꜱᴇ ʙᴇ Pᴀᴛɪᴇɴᴛ, Cᴏᴍᴘʀᴇꜱꜱ ᴡɪʟʟ Sᴛᴀʀᴛ Sᴏᴏɴ", quote=True)
        data.append(message)
        if len(data) == 1:
            await query.delete()   
            
            # Log encoding start
            file_info = {
                'file_id': message.id,
                'file_type': 'video' if message.video else 'document',
                'file_name': getattr(message.video or message.document, 'file_name', 'Unknown'),
                'file_size': getattr(message.video or message.document, 'file_size', 0),
                'timestamp': dt.utcnow()
            }
            log_encoding_activity(
                message.chat.id,
                file_info,
                user_settings,
                'encoding_started'
            )
            
            await add_task(message, user_settings)
            

    @app.on_message(filters.incoming & filters.command(["settings", f"settings@{BOT_USERNAME}"]))
    async def settings(app, message):
        if message.chat.id in AUTH_USERS:
            user_settings = get_user_settings(message.chat.id)
            encoding_stats = get_user_encoding_stats(message.chat.id)
            
            stats_text = ""
            if encoding_stats['total_encodings'] > 0:
                stats_text = (
                    f"\n<b>📊 Your Encoding Stats:</b>\n"
                    f"<blockquote>"
                    f"• <b>Total Encodings:</b> {encoding_stats['total_encodings']}\n"
                    f"• <b>Successful:</b> {encoding_stats['successful_encodings']}\n"
                    f"• <b>Last Activity:</b> {encoding_stats['last_encoding_time'] or 'Never'}\n"
                    f"</blockquote>"
                )
            
            await message.reply_text(
                f"<b>Your Current Settings ⚙️:</b>\n"
                f"<blockquote>"
                f"<b>➥ Quality Profile</b> : {user_settings.get('quality', '720p')}\n"
                f"<b>➥ Codec</b> : {user_settings.get('codec', 'libx264')}\n"
                f"<b>➥ CRF</b> : {user_settings.get('crf', '28')}\n"
                f"<b>➥ Resolution</b> : {user_settings.get('resolution', '1280x720')}\n"
                f"<b>➥ Preset</b> : {user_settings.get('preset', 'veryfast')}\n"
                f"<b>➥ Audio Bitrate</b> : {user_settings.get('audio_b', '40k')}\n"
                f"</blockquote>\n"
                f"{stats_text}\n"
                f"<b>Available Quality Commands:</b>\n"
                f"<code>/360p, /480p, /720p, /1080p, /original</code>\n"
                f"<b>Or use:</b> <code>/quality [profile]</code>"
            )
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")

    @app.on_message(filters.incoming & filters.command(["reset", f"reset@{BOT_USERNAME}"]))
    async def reset_settings(app, message):
        if message.chat.id in AUTH_USERS:
            # Delete user settings to reset to defaults
            success = user_db.delete_user_settings(message.chat.id)
            if success:
                # Log reset activity
                log_encoding_activity(
                    message.chat.id,
                    {'action': 'settings_reset'},
                    user_db.DEFAULT_SETTINGS,
                    'settings_reset'
                )
                await message.reply_text("<blockquote>✅ Settings reset to default</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to reset settings</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
            
    @app.on_message(filters.incoming & filters.command(["stats", f"stats@{BOT_USERNAME}"]))
    async def show_stats(app, message):
        if message.chat.id in AUTH_USERS:
            try:
                # Get user stats from database
                user_stats = user_db.get_user_stats(message.chat.id)
                total_users = user_db.get_users_count()
                encoding_stats = get_user_encoding_stats(message.chat.id)
                
                # Get bot activities count
                if user_db.is_ready():
                    activity_collection = user_db.mongo.get_collection('bot_activities')
                    total_encodings = activity_collection.count_documents({'event': 'encoding_completed'})
                else:
                    total_encodings = 0
                
                stats_text = (
                    f"<b>📊 Bot Statistics</b>\n\n"
                    f"<b>🤖 Bot Uptime:</b> <code>{ts(int((dt.now() - uptime).seconds * 1000))}</code>\n"
                    f"<b>👥 Total Users:</b> <code>{total_users}</code>\n"
                    f"<b>📁 Total Encodings:</b> <code>{total_encodings}</code>\n"
                )
                
                if user_stats:
                    created_at = user_stats.get('created_at', 'N/A')
                    updated_at = user_stats.get('updated_at', 'N/A')
                    
                    stats_text += (
                        f"\n<b>👤 Your Stats:</b>\n"
                        f"<b>Settings Created:</b> <code>{created_at}</code>\n"
                        f"<b>Last Updated:</b> <code>{updated_at}</code>\n"
                        f"<b>Your Encodings:</b> <code>{encoding_stats['total_encodings']}</code>\n"
                        f"<b>Successful:</b> <code>{encoding_stats['successful_encodings']}</code>"
                    )
                
                await message.reply_text(stats_text)
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                await message.reply_text("<blockquote>❌ Error getting statistics</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
            
    @app.on_message(filters.incoming & filters.command(["sysinfo", f"sysinfo@{BOT_USERNAME}"]))
    async def help_message(app, message):
        if message.chat.id in AUTH_USERS:
            await sysinfo(message)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
    @app.on_message(filters.incoming & filters.command(["cancel", f"cancel@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await incoming_cancel_message_f(app, message)
        
    @app.on_message(filters.incoming & filters.command(["exec", f"exec@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await exec_message_f(app, message)
        
    @app.on_message(filters.incoming & filters.command(["eval", f"eval@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await eval_message_f(app, message)
        
    @app.on_message(filters.incoming & filters.command(["stop", f"stop@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await on_task_complete()    
   
    @app.on_message(filters.incoming & filters.command(["help", f"help@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await message.reply_text(
            "Hɪ, ɪ ᴀᴍ <b>Video Encoder bot</b>\n"
            "<blockquote>"
            "➥ Sᴇɴᴅ ᴍᴇ Yᴏᴜʀ Tᴇʟᴇɢʀᴀᴍ Fɪʟᴇꜱ\n"
            "➥ I ᴡɪʟʟ Eɴᴄᴏᴅᴇ ᴛʜᴇᴍ Oɴᴇ ʙʏ Oɴᴇ Aꜱ ɪ Hᴀᴠᴇ <b>Queue Feature</b>\n"
            "➥ Jᴜꜱᴛ Sᴇɴᴅ ᴍᴇ ᴛʜᴇ Jᴘɢ/Pɪᴄ ᴀɴᴅ Iᴛ Wɪʟʟ ʙᴇ Sᴇᴛ ᴀꜱ Yᴏᴜʀ Cᴜꜱᴛᴏᴍ Tʜᴜᴍʙɴᴀɪʟ\n"
            "➥ <b>Quality Commands:</b> <code>/360p, /480p, /720p, /1080p, /original</code>\n"
            "➥ <b>Or use:</b> <code>/quality [profile]</code> to change quality\n"
            "➥ <b>Settings:</b> <code>/settings</code> to view your current settings\n"
            "➥ <b>Reset:</b> <code>/reset</code> to reset to default settings\n"
            "➥ <b>Stats:</b> <code>/stats</code> to view bot statistics\n"
            "➥ <b>Encoding Stats:</b> View your personal encoding history\n"
            "➥ Fᴏʀ FFᴍᴘᴇɢ Lᴏᴠᴇʀꜱ - U ᴄᴀɴ Cʜᴀɴɢᴇ ᴄʀꜰ Bʏ /eval crf.insert(0, 'crf value')"
            "</blockquote>\n"
            "<b>Maintained By : @Rimuru_Wine</b>", 
            quote=True
        )
        
    @app.on_message(filters.incoming & filters.command(["log", f"log@{BOT_USERNAME}"]))
    async def help_message(app, message):
        await upload_log_file(app, message)
        
    @app.on_message(filters.incoming & filters.command(["ping", f"ping@{BOT_USERNAME}"]))
    async def up(app, message):
      stt = dt.now()
      ed = dt.now()
      v = ts(int((ed - uptime).seconds) * 1000)
      u = f"<blockquote>Bᴏᴛ ᴜᴘᴛɪᴍᴇ = {v} 🚀"
      ms = (ed - stt).microseconds / 1000
      p = f"Pɪɴɢ = {ms}ms 🌋</blockquote>"
      await message.reply_text(u + "\n" + p)

    # New command: View encoding history
    @app.on_message(filters.incoming & filters.command(["history", f"history@{BOT_USERNAME}"]))
    async def encoding_history(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
        
        try:
            if user_db.is_ready():
                activity_collection = user_db.mongo.get_collection('encoding_activities')
                recent_activities = activity_collection.find(
                    {'user_id': message.chat.id, 'activity_type': 'encoding'}
                ).sort('timestamp', -1).limit(10)
                
                activities_list = list(recent_activities)
                if activities_list:
                    history_text = "<b>📜 Your Recent Encoding Activities:</b>\n\n"
                    for activity in activities_list:
                        status_emoji = "✅" if activity.get('status') == 'completed' else "⏳" if activity.get('status') == 'encoding_started' else "❌"
                        history_text += (
                            f"{status_emoji} <b>{activity.get('timestamp', 'Unknown').strftime('%Y-%m-%d %H:%M')}</b> - "
                            f"{activity.get('status', 'unknown').replace('_', ' ').title()}\n"
                        )
                    await message.reply_text(history_text)
                else:
                    await message.reply_text("<blockquote>No encoding history found.</blockquote>")
            else:
                await message.reply_text("<blockquote>Database not available.</blockquote>")
        except Exception as e:
            logger.error(f"Error getting encoding history: {e}")
            await message.reply_text("<blockquote>❌ Error retrieving history</blockquote>")

    call_back_button_handler = CallbackQueryHandler(
        button
    )
    app.add_handler(call_back_button_handler)

    # run the APPlication
    app.run()
