import asyncio
import io
import logging
import os
import shutil
import sys
import time
import traceback

from bot import (
    BOT_START_TIME,
    LOGGER,
    LOG_FILE_ZZGEVC,
    MAX_MESSAGE_LENGTH,
    AUTH_USERS,
    crf,
    codec,
    resolution,
    audio_b,
    preset,
    watermark,
    data,
    pid_list
)

from bot.commands import Command
from bot.localisation import Localisation
from bot.helper_funcs.display_progress import (
    TimeFormatter,
    humanbytes
)


async def exec_message_f(client, message):
    if message.from_user.id in AUTH_USERS:
        if True:
            DELAY_BETWEEN_EDITS = 0.3
            PROCESS_RUN_TIME = 100
            cmd = message.text.split(" ", maxsplit=1)[1]

            reply_to_id = message.message_id
            if message.reply_to_message:
                reply_to_id = message.reply_to_message.message_id

            start_time = time.time() + PROCESS_RUN_TIME
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            e = stderr.decode()
            if not e:
                e = "No Error"
            o = stdout.decode()
            if not o:
                o = "No Output"
            else:
                _o = o.split("\n")
                o = "`\n".join(_o)
            OUTPUT = f"<blockquote>**QUERY:**\n__Command:__\n`{cmd}` \n__PID:__\n`{process.pid}`\n\n**stderr:** \n`{e}`\n**Output:**\n{o}</blockquote>"

            if len(OUTPUT) > MAX_MESSAGE_LENGTH:
                with open("exec.text", "w+", encoding="utf8") as out_file:
                    out_file.write(str(OUTPUT))
                await client.send_document(
                    chat_id=message.chat.id,
                    document="exec.text",
                    caption=cmd,
                    disable_notification=True,
                    reply_parameters={"message_id": reply_to_id}  # Fixed deprecated parameter
                )
                os.remove("exec.text")
                await message.delete()
            else:
                await message.reply_text(OUTPUT)
    else:
        return


async def eval_message_f(client, message):
    if message.from_user.id in AUTH_USERS:
        status_message = await message.reply_text("Processing ...⏳")
        cmd = message.text.split(" ", maxsplit=1)[1]

        reply_to_id = message.id
        if message.reply_to_message:
            reply_to_id = message.reply_to_message.id

        old_stderr = sys.stderr
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()
        redirected_error = sys.stderr = io.StringIO()
        stdout, stderr, exc = None, None, None

        try:
            await aexec(cmd, client, message)
        except Exception:
            exc = traceback.format_exc()

        stdout = redirected_output.getvalue()
        stderr = redirected_error.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        evaluation = ""
        if exc:
            evaluation = exc
        elif stderr:
            evaluation = stderr
        elif stdout:
            evaluation = stdout
        else:
            evaluation = "Success"

        final_output = (
            "<blockquote><b>EVAL</b>: <code>{}</code>\n\n<b>OUTPUT</b>:\n<code>{}</code> \n</blockquote>".format(
                cmd, evaluation.strip()
            )
        )

        if len(final_output) > MAX_MESSAGE_LENGTH:
            with open("eval.text", "w+", encoding="utf8") as out_file:
                out_file.write(str(final_output))
            await message.reply_document(
                document="eval.text",
                caption=cmd,
                disable_notification=True,
                reply_parameters={"message_id": reply_to_id},  # Fixed deprecated parameter
            )
            os.remove("eval.text")
            await status_message.delete()
        else:
            await status_message.edit(final_output)


async def aexec(code, client, message):
    exec(
        f"async def __aexec(client, message): "
        + "".join(f"\n {l}" for l in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)


async def upload_log_file(client, message):
    if message.from_user.id in AUTH_USERS:
        try:
            # Check if log file exists
            if not os.path.exists(LOG_FILE_ZZGEVC):
                await message.reply_text("❌ Log file not found.")
                return
            
            # Check if log file has content
            file_size = os.path.getsize(LOG_FILE_ZZGEVC)
            if file_size == 0:
                await message.reply_text("📝 Log file is empty - no recent activity to report.")
                return
            
            # Check if file is too small (might indicate corruption)
            if file_size < 10:  # Less than 10 bytes
                await message.reply_text("⚠️ Log file seems corrupted or incomplete.")
                return
            
            # Upload the log file
            await message.reply_document(
                document=LOG_FILE_ZZGEVC,
                caption=f"📋 Bot Log File\n📊 Size: {humanbytes(file_size)}",
                disable_notification=True
            )
            
        except FileNotFoundError:
            await message.reply_text("❌ Log file not found at the specified path.")
        except PermissionError:
            await message.reply_text("❌ Permission denied accessing log file.")
        except Exception as e:
            LOGGER.error(f"Error uploading log file: {str(e)}")
            await message.reply_text(f"❌ Error uploading log file: {str(e)}")
    else:
        return
