from datetime import datetime as dt
import os, asyncio, pyrogram, psutil, platform
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

from bot.plugins.incoming_message_fn import (
    incoming_start_message_f,
    incoming_compress_message_f,
    incoming_cancel_message_f
)

from bot.plugins.status_message_fn import (
    eval_message_f,
    exec_message_f,
    upload_log_file
)

from bot.commands import Command
from bot.plugins.call_back_button_handler import button
from bot.database import user_db  # Import MongoDB database

sudo_users = "5179011789" 

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
    """Get user settings from database"""
    return user_db.get_user_settings(user_id)

def update_user_settings(user_id: int, **kwargs):
    """Update user settings in database"""
    return user_db.update_user_settings(user_id, **kwargs)

if __name__ == "__main__" :
    # create download directory, if not exist
    if not os.path.isdir(DOWNLOAD_LOCATION):
        os.makedirs(DOWNLOAD_LOCATION)
        
    # STATUS ADMIN Command

    # START command
    incoming_start_message_handler = MessageHandler(
        incoming_start_message_f,
        filters=filters.command(["start", f"start@{BOT_USERNAME}"])
    )
    app.add_handler(incoming_start_message_handler)
    
    @app.on_message(filters.incoming & filters.command(["crf", f"crf@{BOT_USERNAME}"]))
    async def changecrf(app, message):
        if message.chat.id in AUTH_USERS:
            cr = message.text.split(" ", maxsplit=1)[1]
            user_settings = get_user_settings(message.chat.id)
            OUT = f"<blockquote>I will be using : {cr} crf</blockquote>"
            # Update in database
            update_user_settings(message.chat.id, crf=cr)
            await message.reply_text(OUT)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
            

    @app.on_message(filters.incoming & filters.command(["resolution", f"resolution@{BOT_USERNAME}"]))
    async def changer(app, message):
        if message.chat.id in AUTH_USERS:
            r = message.text.split(" ", maxsplit=1)[1]
            OUT = f"<blockquote>I will be using : {r} </blockquote>"
            # Update in database
            update_user_settings(message.chat.id, resolution=r)
            await message.reply_text(OUT)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")

               
    @app.on_message(filters.incoming & filters.command(["preset", f"preset@{BOT_USERNAME}"]))
    async def changepr(app, message):
        if message.chat.id in AUTH_USERS:
            pop = message.text.split(" ", maxsplit=1)[1]
            OUT = f"<blockquote>I will be using : {pop} preset</blockquote>"
            # Update in database
            update_user_settings(message.chat.id, preset=pop)
            await message.reply_text(OUT)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")

            
    @app.on_message(filters.incoming & filters.command(["codec", f"codec@{BOT_USERNAME}"]))
    async def changecode(app, message):
        if message.chat.id in AUTH_USERS:
            col = message.text.split(" ", maxsplit=1)[1]
            OUT = f"<blockquote>I will be using : {col} codec</blockquote>"
            # Update in database
            update_user_settings(message.chat.id, codec=col)
            await message.reply_text(OUT)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
             
    @app.on_message(filters.incoming & filters.command(["audio", f"audio@{BOT_USERNAME}"]))
    async def changea(app, message):
        if message.chat.id in AUTH_USERS:
            aud = message.text.split(" ", maxsplit=1)[1]
            OUT = f"<blockquote>I will be using : {aud} audio</blockquote>"
            # Update in database
            update_user_settings(message.chat.id, audio_b=aud)
            await message.reply_text(OUT)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
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
            success = user_db.update_quality_profile(message.chat.id, quality)
            if success:
                profile = user_db.QUALITY_PROFILES[quality]
                quality_info = (
                    f"<b>Quality changed to:</b> <code>{quality.upper()}</code>\n\n"
                    f"<b>Settings Applied:</b>\n"
                    f"• <b>Resolution:</b> <code>{profile['resolution']}</code>\n"
                    f"• <b>CRF:</b> <code>{profile['crf']}</code>\n"
                    f"• <b>Audio:</b> <code>{profile['audio']}</code>"
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
            success = user_db.update_quality_profile(message.chat.id, "360p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 360p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["480p", f"480p@{BOT_USERNAME}"]))
    async def set_480p(app, message):
        if message.chat.id in AUTH_USERS:
            success = user_db.update_quality_profile(message.chat.id, "480p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 480p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["720p", f"720p@{BOT_USERNAME}"]))
    async def set_720p(app, message):
        if message.chat.id in AUTH_USERS:
            success = user_db.update_quality_profile(message.chat.id, "720p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 720p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["1080p", f"1080p@{BOT_USERNAME}"]))
    async def set_1080p(app, message):
        if message.chat.id in AUTH_USERS:
            success = user_db.update_quality_profile(message.chat.id, "1080p")
            if success:
                await message.reply_text("<blockquote>✅ Quality set to 1080p</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to update quality</blockquote>")
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
    
    @app.on_message(filters.incoming & filters.command(["original", f"original@{BOT_USERNAME}"]))
    async def set_original(app, message):
        if message.chat.id in AUTH_USERS:
            success = user_db.update_quality_profile(message.chat.id, "original")
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
        user_settings = get_user_settings(message.chat.id)
        
        query = await message.reply_text("Aᴅᴅᴇᴅ Tᴏ Qᴜᴇᴜᴇ ⏰...\nPʟᴇᴀꜱᴇ ʙᴇ Pᴀᴛɪᴇɴᴛ, Cᴏᴍᴘʀᴇꜱꜱ ᴡɪʟʟ Sᴛᴀʀᴛ Sᴏᴏɴ", quote=True)
        data.append(message.reply_to_message)
        if len(data) == 1:
         await query.delete()   
         await add_task(message.reply_to_message)     
 
    @app.on_message(filters.incoming & filters.command(["restart", f"restart@{BOT_USERNAME}"]))
    async def restarter(app, message):
        if message.chat.id in AUTH_USERS:
            await message.reply_text("Rᴇꜱᴛᴀʀᴛɪɴɢ...♻️")
            quit(1)
        else:
            await message.reply_text("<blockquote>Aᴅᴍɪɴ Oɴʟʏ 🔒</blockquote>")
            
    @app.on_message(filters.incoming & filters.command(["clear", f"clear@{BOT_USERNAME}"]))
    async def restarter(app, message):
        data.clear()
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪꜱᴇᴅ Tᴏ Uꜱᴇ Tʜɪꜱ Bᴏᴛ Cᴏɴᴛᴀᴄᴛ @Lord_Vasudev_Krishna</blockquote>")
        query = await message.reply_text("<blockquote>Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʟᴇᴀʀᴇᴅ Qᴜᴇᴜᴇ...📚</blockquote>")
      
        
    @app.on_message(filters.incoming & (filters.video | filters.document))
    async def help_message(app, message):
        if message.chat.id not in AUTH_USERS:
            return await message.reply_text("<blockquote>Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪꜱᴇᴅ Tᴏ Uꜱᴇ Tʜɪꜱ Bᴏᴛ Cᴏɴᴛᴀᴄᴛ @Itz_Sizian</blockquote>")
        
        # Get user settings for encoding
        user_settings = get_user_settings(message.chat.id)
        
        query = await message.reply_text("Aᴅᴅᴇᴅ Tᴏ Qᴜᴇᴜᴇ ⏰...\nPʟᴇᴀꜱᴇ ʙᴇ Pᴀᴛɪᴇɴᴛ, Cᴏᴍᴘʀᴇꜱꜱ ᴡɪʟʟ Sᴛᴀʀᴛ Sᴏᴏɴ", quote=True)
        data.append(message)
        if len(data) == 1:
         await query.delete()   
         await add_task(message)
            

    @app.on_message(filters.incoming & filters.command(["settings", f"settings@{BOT_USERNAME}"]))
    async def settings(app, message):
        if message.chat.id in AUTH_USERS:
            user_settings = get_user_settings(message.chat.id)
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
                await message.reply_text("<blockquote>✅ Settings reset to default</blockquote>")
            else:
                await message.reply_text("<blockquote>❌ Failed to reset settings</blockquote>")
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

    call_back_button_handler = CallbackQueryHandler(
        button
    )
    app.add_handler(call_back_button_handler)

    # run the APPlication
    app.run()
