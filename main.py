import sys
import imaplib
import email
import email.header
import datetime
import quopri
import logging
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram import ParseMode
from telegram import Bot
from oauth2 import GenerateOAuth2String
from oauth2 import RefreshToken


class Status:
    job_queue_running = True
    last_subject = ""
    last_body = ""


class Config:
    email_account = "tef.tr62@gmail.com"
    google_client_id = "000000000000.apps.googleusercontent.com"
    google_client_secret = "aAaAaAaAAaAAA0_A-0AaAaAaA"
    google_refresh_token = "1/aAaAaAaAAaAAA0-aAaAaAaAAaAAA0aAaAaAaAAaAAA0"
    last_email_num = 200
    chat_id = "000000000"  # chat id, to where home assignment will be sent
    creator_username = "Samilton"  # username of main admin/creator of bot, write it without '@'
    creator_id = "000000000"  # chat id, of main admin/creator of bot
    token = "000000000:AAAAAAAAA-aaaaaaaaaaaaaaaaaaaaa0000"  # telegram bot token, you can take it from Bot Father


# Global vars
bot = Bot(Config.token)
mail = imaplib.IMAP4_SSL('imap.gmail.com')


def process_mailbox():
    global mail
    try:
        result, data = mail.search(None, '(FROM "lis.kostiantyn@gmail.com" SUBJECT "Home assignment")')
    except imaplib.IMAP4.error as exc:
        print("\nSearching failed!!! Error:", exc, "\n")
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.debug = 4
            response = RefreshToken(Config.google_client_id, Config.google_client_secret, Config.google_refresh_token)
            auth_string = GenerateOAuth2String(Config.email_account, response['access_token'], base64_encode=False)
            mail.authenticate('XOAUTH2', lambda x: auth_string)
        except imaplib.IMAP4.error as exc:
            print("\nLOGIN FAILED!!! Error:", exc, "\n")
            bot.send_message(chat_id=Config.creator_id, text="Login failed!")
            return False, "", ""

        mail.list()
        mail.select("INBOX")
        result, data = mail.search(None, '(FROM "lis.kostiantyn@gmail.com" SUBJECT "Home assignment")')

    if result != 'OK':
        print("No messages found!")
        return

    for num in data[0].split():
        if int(num) <= Config.last_email_num:
            continue

        result, data = mail.fetch(num, '(RFC822)')
        if result != 'OK':
            print("\n\nERROR: getting message №", num, "\n\n")
            continue

        try:
            msg = email.message_from_bytes(data[0][1])
        except Exception as e:
            print("\n\nERROR: making message\n\n")
            continue

        try:
            hdr = email.header.make_header(email.header.decode_header(msg['Subject']))
            subject = str(hdr)
        except Exception as e:
            print("\n\nWARNING: making header\n")
            subject = "nil"

        print('Message %s: %s' % (num, subject))
        print('Raw Date:', msg['Date'])

        date_tuple = email.utils.parsedate_tz(msg['Date'])
        if date_tuple:
            local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            print("Local Date:", local_date.strftime("%a, %d %b %Y %H:%M:%S"))

        if msg.is_multipart():
            body = ""
            for payload in msg.get_payload():
                body += payload.get_payload()
        else:
            body = msg.get_payload()

        body = quopri.decodestring(body)
        body = body.decode('windows-1251')

        if body.startswith("Здравствуйте, ."):
            body = body.partition("Здравствуйте, .")
            body = body[2].strip()
        else:
            body = body.strip()

        if body.endswith("mailto:lis.kostiantyn@gmail.com"):
            body = body.partition("--")
            body = body[0].strip()
        else:
            body = body.strip()

        if body.find("All the materials are here") != -1:
            body = body.partition("All the materials are here")
            body = body[0].strip() + '\n\n' + body[1] + body[2]

        print("Body:\n" + body + '\n')

        Config.last_email_num = int(num)
        return True, subject, body

    return False, "", ""


def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN,
                     text="I'm an English Home Assignment bot. I can notify you or group/channel about new english "
                          "home assignment from gmail box.\n\n"

                          "Available commands:\n"
                          "/status - Check auto checking status\n"
                          "/check - Manually check new home assignment or send last one, "
                          "even if auto checking is off\n\n"

                          "Commands just for creator:\n"
                          "/startchecking - Start auto checking email\n"
                          "/stopchecking - Stop auto checking email\n"
                          "/setchatid - Set chat ID, where home assignment will be displayed\n"
                          "/setlastnum - Set last sended email number\n"
                          "/setinterval - Set interval between auto checking\n\n"

                          "My creator is - @Samilton\n"
                          "[My code on GitHub](https://github.com/Oradle/GmailToTelegramBot)")


def start_checking(bot, update, job_queue):
    if update.message.from_user['username'] == Config.creator_username:
        if Status.job_queue_running:
            bot.send_message(chat_id=update.message.chat_id, text="Email checking are already running")
        else:
            job_queue.jobs()[0].enabled = True
            bot.send_message(chat_id=update.message.chat_id, text="Email checking was started")
            Status.job_queue_running = True
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="You aren't my creator, ask my creator - @" + Config.creator_username + " to do this")


def stop_checking(bot, update, job_queue):
    if update.message.from_user['username'] == Config.creator_username:
        if Status.job_queue_running:
            job_queue.jobs()[0].enabled = False
            bot.send_message(chat_id=update.message.chat_id, text="Email checking was stopped")
            Status.job_queue_running = False
        else:
            bot.send_message(chat_id=update.message.chat_id, text="Email checking are already stopped")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="You aren't my creator, ask my creator - @" + Config.creator_username + " to do this")


def check_email_manually(bot, update):
    success, subject, body = process_mailbox()
    if success:
        bot.send_message(chat_id=Config.chat_id, text='*' + subject + '*' + "\n\n" + body,
                         parse_mode=ParseMode.MARKDOWN)
        bot.send_message(chat_id=update.message.chat_id, text="Successfully added new email")

        Status.last_body = body
        Status.last_subject = subject
    else:
        bot.send_message(chat_id=update.message.chat_id, text="Nothing new. The last one was:")
        bot.send_message(chat_id=update.message.chat_id,
                         text='*' + Status.last_subject + '*' + "\n\n" + Status.last_body,
                         parse_mode=ParseMode.MARKDOWN)


def check_job_status(bot, update):
    if Status.job_queue_running:
        bot.send_message(chat_id=update.message.chat_id, text="Email checking is running")
    else:
        bot.send_message(chat_id=update.message.chat_id, text="Email checking stopped")


def set_chat_id(bot, update, args):
    if update.message.from_user['username'] == Config.creator_username:
        Config.chat_id = args[0]
        bot.send_message(chat_id=update.message.chat_id, text="Chat id successfully changed")
        print("\nChat id was changed to " + str(Config.chat_id) + "\n")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="You aren't my creator, ask my creator - @" + Config.creator_username + " to do this")


def set_last_email_num(bot, update, args):
    if update.message.from_user['username'] == Config.creator_username:
        Config.last_email_num = int(args[0])
        bot.send_message(chat_id=update.message.chat_id, text="Last email number successfully changed")
        print("\nLast email number was changed to " + str(Config.last_email_num) + "\n")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="You aren't my creator, ask my creator - @" + Config.creator_username + " to do this")


def set_checking_interval(bot, update, job_queue, args):
    if update.message.from_user['username'] == Config.creator_username:
        job_queue.jobs()[0].interval = int(args[0])
        bot.send_message(chat_id=update.message.chat_id, text="Checking interval successfully changed")
        print("\nChecking interval was changed to " + str(int(args[0])) + "\n")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="You aren't my creator, ask my creator - @" + Config.creator_username + " to do this")


def email_checking_callback(bot, job):
    success, subject, body = process_mailbox()
    if success:
        bot.send_message(chat_id=Config.chat_id,
                         text='*' + subject + '*' + "\n\n" + body + "\n\n_via_ @EnglishHomeAssignmentBot",
                         parse_mode=ParseMode.MARKDOWN)

        Status.last_body = body
        Status.last_subject = subject
    else:
        print("\nNothing new\n")


def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

    updater = Updater(Config.token)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    global mail
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.debug = 4
        response = RefreshToken(Config.google_client_id, Config.google_client_secret, Config.google_refresh_token)
        auth_string = GenerateOAuth2String(Config.email_account, response['access_token'], base64_encode=False)
        mail.authenticate('XOAUTH2', lambda x: auth_string)
    except imaplib.IMAP4.error as exc:
        print("\nLOGIN FAILED!!! Error:", exc, "\n")
        sys.exit(1)

    print("Processing mailbox...\n")
    bot.send_message(chat_id=Config.creator_id, text="Bot loading...")

    mail.list()
    mail.select("INBOX")

    job_queue.run_repeating(email_checking_callback, interval=15, first=0, name="email_checking")  # 900

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    stop_checking_handler = CommandHandler('stopchecking', stop_checking, pass_job_queue=True)
    dispatcher.add_handler(stop_checking_handler)

    start_checking_handler = CommandHandler('startchecking', start_checking, pass_job_queue=True)
    dispatcher.add_handler(start_checking_handler)

    check_email_manually_handler = CommandHandler('check', check_email_manually)
    dispatcher.add_handler(check_email_manually_handler)

    check_job_status_handler = CommandHandler('status', check_job_status)
    dispatcher.add_handler(check_job_status_handler)

    set_chat_id_handler = CommandHandler('setchatid', set_chat_id, pass_args=True)
    dispatcher.add_handler(set_chat_id_handler)

    set_last_email_num_handler = CommandHandler('setlastnum', set_last_email_num, pass_args=True)
    dispatcher.add_handler(set_last_email_num_handler)

    set_checking_interval_handler = CommandHandler('setinterval', set_checking_interval, pass_job_queue=True,
                                                   pass_args=True)
    dispatcher.add_handler(set_checking_interval_handler)

    job_queue.start()
    updater.start_polling()


if __name__ == "__main__":
    main()