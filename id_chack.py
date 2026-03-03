import telebot

# BotFather에게 받은 토큰을 입력하세요
API_TOKEN = '8229177734:AAHAqZKjQUzUYTuJTXagvqhDLCzkJcbmVxI'
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(func=lambda message: True)
def get_id(message):
    # 메시지를 보낸 사람의 숫자 ID를 출력
    print(f"사용자 이름: {message.from_user.first_name}")
    print(f"사용자 숫자 ID: {message.from_user.id}")
    bot.reply_to(message, f"기장님의 ID는 {message.from_user.id}입니다.")

bot.polling()