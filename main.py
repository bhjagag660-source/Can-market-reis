#                     WALES MARKET BOT
#                   @HollandaBaskan tarafından
# ═══════════════════════════════════════════════════════════════

from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMember
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes,
    CallbackQueryHandler, filters
)
from datetime import datetime, date
import asyncio

# ───────────────────────────────────────────────────────────────
# AYARLAR
# ───────────────────────────────────────────────────────────────

TOKEN        = "8694381551:AAFLPA7fCZCnbEDtIQ54gU9tpa-xGTm1Q3o"
ADMIN_ID     = 8230214476
BOT_USERNAME = "AhmetMarketBot"
KANAL_ADI    = "@canmasterarsiv"
KANAL_LINK   = "https://t.me/canmasterarsiv"
DESTEK       = "@HollandaBaskan"

# ───────────────────────────────────────────────────────────────
# VERİ YAPILARI  (in-memory — bot yeniden başlatılırsa sıfırlanır)
# ───────────────────────────────────────────────────────────────

users              = {}   # {user_id: {ref, ref_sayisi, kayit_tarihi, son_gunluk}}
banned             = set()
satin_alma_gecmisi = {}   # {user_id: [ {urun, fiyat, tarih}, ... ]}
transfer_gecmisi   = {}   # {user_id: [ {hedef, miktar, tarih}, ... ]}

products = {
    "buy_pubg":   {"ad": "🍗 PUBG Kesin Giriş",        "fiyat": 15},
    "buy_brawl":  {"ad": "🌵 Brawl Stars Kesin Giriş",  "fiyat": 10},
    "buy_roblox": {"ad": "💎 Roblox 100 Robux",         "fiyat": 10},
    "buy_wp":     {"ad": "📞 WhatsApp Fake No",          "fiyat": 10},
    "buy_tg":     {"ad": "📱 Telegram Fake No",          "fiyat": 15},
    "buy_panel":  {"ad": "📂 Panel Erişimi",             "fiyat": 15},
    "buy_uye":    {"ad": "📊 100 TG Üye",               "fiyat":  8},
    "buy_steam":  {"ad": "🎮 Steam Fake No",             "fiyat": 12},
    "buy_insta":  {"ad": "📷 Instagram Fake No",         "fiyat": 10},
    "buy_valorant":{"ad":"🔫 Valorant Hesap",            "fiyat": 20},
}

# ───────────────────────────────────────────────────────────────
# YARDIMCI  —  kullanıcı kaydı
# ───────────────────────────────────────────────────────────────

def kullanici_olustur(uid: int):
    """Kullanıcı kaydı yoksa oluşturur."""
    if uid not in users:
        users[uid] = {
            "ref":          0,
            "ref_sayisi":   0,
            "kayit_tarihi": str(date.today()),
            "son_gunluk":   None,
        }
    if uid not in satin_alma_gecmisi:
        satin_alma_gecmisi[uid] = []
    if uid not in transfer_gecmisi:
        transfer_gecmisi[uid] = []


# ───────────────────────────────────────────────────────────────
# YARDIMCI  —  kanal kontrolü
# ───────────────────────────────────────────────────────────────

async def kanal_kontrol(uid: int, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Kullanıcının kanala üye olup olmadığını kontrol eder."""
    try:
        m = await ctx.bot.get_chat_member(KANAL_ADI, uid)
        return m.status in (
            ChatMember.MEMBER,
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER,
        )
    except Exception:
        return False


async def kanal_engel(update: Update):
    """Üye olmayan kullanıcıya uyarı + katıl butonu gönderir."""
    btn = [[InlineKeyboardButton("📢 Kanala Katıl", url=KANAL_LINK)]]
    await update.message.reply_text(
        f"⚠️ Botu kullanmak için {KANAL_ADI} kanalına katılman gerekiyor!\n\n"
        "Katıldıktan sonra tekrar /start yaz.",
        reply_markup=InlineKeyboardMarkup(btn),
    )


# ───────────────────────────────────────────────────────────────
# KLAVYE YARDIMCILARI
# ───────────────────────────────────────────────────────────────

def ana_menu(uid: int) -> ReplyKeyboardMarkup:
    kb = [
        ["🛒 Market",          "👤 Profilim"],
        ["🔗 Referans Linkim", "🎁 Günlük Ödül"],
        ["🏆 Liderlik",        "📦 Geçmişim"],
        ["💸 Ref Transfer",    "📊 Bakiyem"],
    ]
    if uid == ADMIN_ID:
        kb.append(["⚙️ Admin Panel"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    kb = [
        ["➕ Ref Ver",    "➖ Ref Sil"],
        ["🚫 Ban",        "✅ Unban"],
        ["📊 İstatistik", "👥 Kullanıcı Ara"],
        ["📣 Toplu Mesaj","🔙 Geri"],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def market_kb() -> InlineKeyboardMarkup:
    btns = []
    for key, v in products.items():
        btns.append([InlineKeyboardButton(
            f"{v['ad']}  ·  {v['fiyat']} Ref",
            callback_data=key,
        )])
    return InlineKeyboardMarkup(btns)


def liderlik_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Yenile", callback_data="refresh_lider")
    ]])


def profil_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Market",         callback_data="goto_market")],
        [InlineKeyboardButton("🔗 Referans Linkim",callback_data="goto_ref")],
    ])


# ───────────────────────────────────────────────────────────────
# YARDIMCI  —  liderlik metni üret
# ───────────────────────────────────────────────────────────────

def liderlik_metni(gorunen_uid: int) -> str:
    if not users:
        return "📊 Henüz kayıtlı kullanıcı yok."
    sirali   = sorted(users.items(), key=lambda x: x[1]["ref"], reverse=True)
    top10    = sirali[:10]
    madalya  = ["🥇", "🥈", "🥉"]
    metin    = "🏆 *LİDERLİK TABLOSU*\n\n"
    for i, (uid, d) in enumerate(top10):
        simge   = madalya[i] if i < 3 else f"  {i+1}."
        isaretli = "  👈 Sen" if uid == gorunen_uid else ""
        metin   += f"{simge} `{uid}`  —  `{d['ref']}` Ref{isaretli}\n"
    tum = sorted(users.items(), key=lambda x: x[1]["ref"], reverse=True)
    sira = next((i+1 for i,(uid,_) in enumerate(tum) if uid == gorunen_uid), "-")
    metin += f"\n━━━━━━━━━━━━━━━━━━\n"
    metin += f"📊 Senin sıran: `{sira}` / `{len(users)}`"
    return metin


# ───────────────────────────────────────────────────────────────
# /start
# ───────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.message.from_user.id
    isim  = update.message.from_user.first_name or "Kullanıcı"

    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")

    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)

    yeni = uid not in users
    kullanici_olustur(uid)

    # ── Referans ──────────────────────────────
    if ctx.args and yeni:
        try:
            ref_id = int(ctx.args[0])
            if ref_id != uid and ref_id in users:
                users[ref_id]["ref"]        += 1
                users[ref_id]["ref_sayisi"] += 1
                try:
                    await ctx.bot.send_message(
                        chat_id=ref_id,
                        text=(
                            f"🎉 Birileri davetinle katıldı!\n"
                            f"+1 Ref kazandın 💰\n"
                            f"Güncel bakiye: `{users[ref_id]['ref']}` Ref"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
        except Exception:
            pass

    hosgeldin = f"🎉 Hoş geldin, {isim}!" if yeni else f"👋 Tekrar hoş geldin, {isim}!"

    await update.message.reply_text(
        f"{hosgeldin}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 Referans toplayarak marketten ürün satın alabilirsin.\n"
        f"📢 Kanal: {KANAL_ADI}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Menüden istediğin işlemi seç.",
        reply_markup=ana_menu(uid),
    )


# ───────────────────────────────────────────────────────────────
# MARKET
# ───────────────────────────────────────────────────────────────

async def market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)
    ref = users[uid]["ref"]
    await update.message.reply_text(
        "🛒 *WALES MARKET*\n\n"
        f"💰 Bakiyen: `{ref}` Ref\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Bir ürün seç, satın al!\n"
        f"Teslimat için: {DESTEK}\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=market_kb(),
    )


async def satin_al_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ürün satın alma callback'i."""
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid in banned:
        return await q.message.reply_text("🚫 Yasaklısın!")
    if q.data not in products:
        return

    kullanici_olustur(uid)
    urun   = products[q.data]
    fiyat  = urun["fiyat"]
    ad     = urun["ad"]
    bakiye = users[uid]["ref"]

    if bakiye >= fiyat:
        users[uid]["ref"] -= fiyat
        satin_alma_gecmisi[uid].append({
            "urun":  ad,
            "fiyat": fiyat,
            "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
        })
        await q.message.reply_text(
            f"✅ *Satın Alma Başarılı!*\n\n"
            f"🛍 Ürün  : {ad}\n"
            f"💸 Harcanan : `{fiyat}` Ref\n"
            f"💰 Kalan    : `{users[uid]['ref']}` Ref\n\n"
            f"📩 Teslim için {DESTEK}'a yaz.",
            parse_mode="Markdown",
        )
    else:
        eksik = fiyat - bakiye
        await q.message.reply_text(
            f"❌ *Yetersiz Bakiye!*\n\n"
            f"💰 Bakiyen : `{bakiye}` Ref\n"
            f"💸 Gereken : `{fiyat}` Ref\n"
            f"⚠️ Eksik   : `{eksik}` Ref\n\n"
            "🔗 Referans linkini paylaşarak bakiye kazan!",
            parse_mode="Markdown",
        )


# ───────────────────────────────────────────────────────────────
# PROFİL
# ───────────────────────────────────────────────────────────────

async def profil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)

    u       = users[uid]
    gecmis  = satin_alma_gecmisi[uid]
    son     = gecmis[-1]["urun"] if gecmis else "Henüz yok"
    sirali  = sorted(users.items(), key=lambda x: x[1]["ref"], reverse=True)
    sira    = next((i+1 for i,(x,_) in enumerate(sirali) if x == uid), "-")
    harcama = sum(k["fiyat"] for k in gecmis)

    await update.message.reply_text(
        f"👤 *PROFİLİM*\n\n"
        f"🆔 ID              : `{uid}`\n"
        f"💰 Bakiye          : `{u['ref']}` Ref\n"
        f"👥 Davet Ettiğin   : `{u['ref_sayisi']}` kişi\n"
        f"📅 Kayıt Tarihi    : `{u['kayit_tarihi']}`\n"
        f"🛒 Son Alışveriş   : `{son}`\n"
        f"📦 Toplam Sipariş  : `{len(gecmis)}`\n"
        f"💸 Toplam Harcama  : `{harcama}` Ref\n"
        f"🏆 Genel Sıralama  : `{sira}` / `{len(users)}`",
        parse_mode="Markdown",
        reply_markup=profil_kb(),
    )


# ───────────────────────────────────────────────────────────────
# BAKİYEM  (hızlı bakiye sorgulama)
# ───────────────────────────────────────────────────────────────

async def bakiyem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)
    await update.message.reply_text(
        f"💰 *BAKİYEN*\n\n`{users[uid]['ref']}` Ref",
        parse_mode="Markdown",
    )


# ───────────────────────────────────────────────────────────────
# ALIŞVERİŞ GEÇMİŞİ
# ───────────────────────────────────────────────────────────────

async def gecmis_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)

    gecmis = satin_alma_gecmisi[uid]
    if not gecmis:
        return await update.message.reply_text(
            "📦 *GEÇMİŞİM*\n\nHenüz alışveriş yapmadın.\n🛒 Markete git ve ürün satın al!",
            parse_mode="Markdown",
        )

    metin   = "📦 *ALIŞVERİŞ GEÇMİŞİM* (Son 10)\n\n"
    son10   = gecmis[-10:][::-1]
    for i, k in enumerate(son10, 1):
        metin += f"{i}. {k['urun']}\n   💸 `{k['fiyat']}` Ref  📅 `{k['tarih']}`\n\n"

    harcama = sum(k["fiyat"] for k in gecmis)
    metin  += f"━━━━━━━━━━━━━━━━━━\n"
    metin  += f"💸 Toplam Harcama : `{harcama}` Ref\n"
    metin  += f"📦 Toplam Sipariş : `{len(gecmis)}`"

    await update.message.reply_text(metin, parse_mode="Markdown")


# ───────────────────────────────────────────────────────────────
# REFERANS
# ───────────────────────────────────────────────────────────────

async def referans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)

    link        = f"https://t.me/{BOT_USERNAME}?start={uid}"
    ref_sayisi  = users[uid]["ref_sayisi"]
    ref_bakiye  = users[uid]["ref"]
    paylasim    = f"https://t.me/share/url?url={link}&text=Bu%20bota%20katıl%20ve%20kazanmaya%20başla!"

    btns = [[InlineKeyboardButton("📤 Linki Paylaş", url=paylasim)]]
    await update.message.reply_text(
        f"🔗 *REFERANS LİNKİN*\n\n"
        f"`{link}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Davet Ettiğin : `{ref_sayisi}` kişi\n"
        f"💰 Bakiyen       : `{ref_bakiye}` Ref\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Her davet = +1 Ref 🎁\n"
        f"Daha fazla davet et, daha fazla kazan!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns),
    )


# ───────────────────────────────────────────────────────────────
# GÜNLÜK ÖDÜL
# ───────────────────────────────────────────────────────────────

async def gunluk_odul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)

    bugun = str(date.today())
    if users[uid]["son_gunluk"] == bugun:
        await update.message.reply_text(
            "⏰ *Günlük Ödül*\n\n"
            "Bugünkü ödülünü zaten aldın!\n"
            "Yarın tekrar gel 😊\n\n"
            f"💰 Bakiyen: `{users[uid]['ref']}` Ref",
            parse_mode="Markdown",
        )
    else:
        users[uid]["ref"]        += 1
        users[uid]["son_gunluk"]  = bugun
        await update.message.reply_text(
            f"🎁 *Günlük Ödül Alındı!*\n\n"
            f"+1 Ref kazandın 🎉\n"
            f"💰 Yeni Bakiye : `{users[uid]['ref']}` Ref\n\n"
            "Yarın tekrar gel! 🔥",
            parse_mode="Markdown",
        )


# ───────────────────────────────────────────────────────────────
# LİDERLİK
# ───────────────────────────────────────────────────────────────

async def liderlik(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    await update.message.reply_text(
        liderlik_metni(uid),
        parse_mode="Markdown",
        reply_markup=liderlik_kb(),
    )


# ───────────────────────────────────────────────────────────────
# REF TRANSFER
# ───────────────────────────────────────────────────────────────

async def ref_transfer_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")
    if not await kanal_kontrol(uid, ctx):
        return await kanal_engel(update)
    kullanici_olustur(uid)
    ctx.user_data["islem"] = "transfer"
    await update.message.reply_text(
        "💸 *REF TRANSFER*\n\n"
        "Format: `hedef_id miktar`\n"
        "Örnek:  `123456789 5`\n\n"
        f"💰 Mevcut Bakiyen: `{users[uid]['ref']}` Ref",
        parse_mode="Markdown",
    )


async def ref_transfer_isle(uid: int, text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Transfer işlemini gerçekleştirir."""
    kullanici_olustur(uid)
    try:
        hedef_id, miktar = map(int, text.split())
    except ValueError:
        return await update.message.reply_text("❌ Hatalı format! Örnek: `123456789 5`", parse_mode="Markdown")

    if hedef_id == uid:
        return await update.message.reply_text("❌ Kendine transfer yapamazsın!")
    if miktar <= 0:
        return await update.message.reply_text("❌ Geçersiz miktar!")
    if hedef_id not in users:
        return await update.message.reply_text("❌ Hedef kullanıcı bulunamadı.")
    if users[uid]["ref"] < miktar:
        return await update.message.reply_text(
            f"❌ Yetersiz bakiye!\n💰 Bakiyen: `{users[uid]['ref']}` Ref",
            parse_mode="Markdown",
        )

    users[uid]["ref"]       -= miktar
    users[hedef_id]["ref"]  += miktar
    simdi = datetime.now().strftime("%d.%m.%Y %H:%M")
    transfer_gecmisi[uid].append({"hedef": hedef_id, "miktar": miktar, "tarih": simdi})

    await update.message.reply_text(
        f"✅ Transfer tamamlandı!\n\n"
        f"📤 Gönderilen : `{miktar}` Ref → `{hedef_id}`\n"
        f"💰 Kalan      : `{users[uid]['ref']}` Ref",
        parse_mode="Markdown",
    )
    try:
        await ctx.bot.send_message(
            chat_id=hedef_id,
            text=f"📥 `{uid}` kullanıcısından `{miktar}` Ref aldın!\n💰 Yeni Bakiye: `{users[hedef_id]['ref']}` Ref",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ───────────────────────────────────────────────────────────────
# ADMIN PANELİ
# ───────────────────────────────────────────────────────────────

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *Admin Panel*\n\nBir işlem seç:",
        parse_mode="Markdown",
        reply_markup=admin_menu(),
    )


# ───────────────────────────────────────────────────────────────
# CALLBACK HANDLER
# ───────────────────────────────────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data in products:
        return await satin_al_cb(update, ctx)

    elif q.data == "goto_market":
        kullanici_olustur(uid)
        await q.message.reply_text(
            f"🛒 *WALES MARKET*\n\n💰 Bakiyen: `{users[uid]['ref']}` Ref\n\nBir ürün seç:",
            parse_mode="Markdown",
            reply_markup=market_kb(),
        )

    elif q.data == "goto_ref":
        kullanici_olustur(uid)
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        btns = [[InlineKeyboardButton("📤 Paylaş", url=f"https://t.me/share/url?url={link}")]]
        await q.message.reply_text(
            f"🔗 *REFERANS LİNKİN*\n\n`{link}`\n\n"
            f"👥 Davet: `{users[uid]['ref_sayisi']}`  💰 Bakiye: `{users[uid]['ref']}` Ref",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns),
        )

    elif q.data == "refresh_lider":
        metin = liderlik_metni(uid)
        try:
            await q.message.edit_text(metin, parse_mode="Markdown", reply_markup=liderlik_kb())
        except Exception:
            await q.message.reply_text(metin, parse_mode="Markdown", reply_markup=liderlik_kb())


# ───────────────────────────────────────────────────────────────
# ANA MESAJ HANDLER
# ───────────────────────────────────────────────────────────────

async def mesaj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.message.from_user.id
    text = update.message.text

    if uid in banned:
        return await update.message.reply_text("🚫 Yasaklısın!")

    # ── Ana Menü ─────────────────────────────────────────
    if   text == "🛒 Market":          return await market(update, ctx)
    elif text == "👤 Profilim":        return await profil(update, ctx)
    elif text == "🔗 Referans Linkim": return await referans(update, ctx)
    elif text == "🎁 Günlük Ödül":     return await gunluk_odul(update, ctx)
    elif text == "🏆 Liderlik":        return await liderlik(update, ctx)
    elif text == "📦 Geçmişim":        return await gecmis_cmd(update, ctx)
    elif text == "💸 Ref Transfer":    return await ref_transfer_cmd(update, ctx)
    elif text == "📊 Bakiyem":         return await bakiyem(update, ctx)
    elif text == "🔙 Geri":            return await start(update, ctx)
    elif text == "⚙️ Admin Panel" and uid == ADMIN_ID:
        return await admin_panel(update, ctx)

    # ── Admin Butonları ───────────────────────────────────
    elif text == "➕ Ref Ver" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "refver"
        return await update.message.reply_text(
            "📝 Format: `ID miktar`\nÖrnek: `123456789 10`", parse_mode="Markdown"
        )
    elif text == "➖ Ref Sil" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "refsil"
        return await update.message.reply_text(
            "📝 Format: `ID miktar`\nÖrnek: `123456789 5`", parse_mode="Markdown"
        )
    elif text == "🚫 Ban" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "ban"
        return await update.message.reply_text("📝 Banlanacak kullanıcı ID'si:")
    elif text == "✅ Unban" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "unban"
        return await update.message.reply_text("📝 Banı kaldırılacak kullanıcı ID'si:")
    elif text == "👥 Kullanıcı Ara" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "ara"
        return await update.message.reply_text("📝 Sorgulanacak kullanıcı ID'si:")
    elif text == "📣 Toplu Mesaj" and uid == ADMIN_ID:
        ctx.user_data["islem"] = "toplu"
        return await update.message.reply_text("📝 Tüm kullanıcılara gönderilecek mesajı yaz:")
    elif text == "📊 İstatistik" and uid == ADMIN_ID:
        toplam_ref      = sum(u["ref"] for u in users.values())
        toplam_alisv    = sum(len(v) for v in satin_alma_gecmisi.values())
        en_zengin       = max(users.items(), key=lambda x: x[1]["ref"], default=(0,{"ref":0}))
        return await update.message.reply_text(
            f"📊 *BOT İSTATİSTİKLERİ*\n\n"
            f"👥 Toplam Kullanıcı : `{len(users)}`\n"
            f"🚫 Banlı            : `{len(banned)}`\n"
            f"💰 Aktif Toplam Ref : `{toplam_ref}`\n"
            f"🛒 Toplam Alışveriş : `{toplam_alisv}`\n"
            f"📦 Toplam Ürün      : `{len(products)}`\n"
            f"🏆 En Zengin        : `{en_zengin[0]}` (`{en_zengin[1]['ref']}` Ref)",
            parse_mode="Markdown",
        )

    # ── Admin İşlem Tamamlama ─────────────────────────────
    elif "islem" in ctx.user_data and uid == ADMIN_ID:
        islem = ctx.user_data["islem"]
        try:
            if islem == "refver":
                hedef, miktar = map(int, text.split())
                kullanici_olustur(hedef)
                users[hedef]["ref"] += miktar
                await update.message.reply_text(
                    f"✅ `{hedef}` kullanıcısına `{miktar}` Ref verildi.\n"
                    f"💰 Yeni bakiye: `{users[hedef]['ref']}` Ref",
                    parse_mode="Markdown",
                )
                try:
                    await ctx.bot.send_message(
                        chat_id=hedef,
                        text=f"🎁 Hesabına `{miktar}` Ref eklendi!\n💰 Yeni bakiyen: `{users[hedef]['ref']}` Ref",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

            elif islem == "refsil":
                hedef, miktar = map(int, text.split())
                if hedef in users:
                    once = users[hedef]["ref"]
                    users[hedef]["ref"] = max(0, once - miktar)
                    await update.message.reply_text(
                        f"✅ `{hedef}` kullanıcısından `{miktar}` Ref silindi.\n"
                        f"💰 `{once}` → `{users[hedef]['ref']}` Ref",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text("❌ Kullanıcı bulunamadı.")

            elif islem == "ban":
                hedef = int(text)
                banned.add(hedef)
                await update.message.reply_text(f"🚫 `{hedef}` banlandı.", parse_mode="Markdown")

            elif islem == "unban":
                hedef = int(text)
                if hedef in banned:
                    banned.discard(hedef)
                    await update.message.reply_text(f"✅ `{hedef}` banı kaldırıldı.", parse_mode="Markdown")
                else:
                    await update.message.reply_text(f"ℹ️ `{hedef}` zaten banlı değil.", parse_mode="Markdown")

            elif islem == "ara":
                hedef = int(text)
                if hedef in users:
                    u       = users[hedef]
                    banlimi = "🚫 Evet" if hedef in banned else "✅ Hayır"
                    gs      = satin_alma_gecmisi.get(hedef, [])
                    harcama = sum(k["fiyat"] for k in gs)
                    sirali  = sorted(users.items(), key=lambda x: x[1]["ref"], reverse=True)
                    sira    = next((i+1 for i,(x,_) in enumerate(sirali) if x == hedef), "-")
                    await update.message.reply_text(
                        f"👤 *KULLANICI BİLGİSİ*\n\n"
                        f"🆔 ID             : `{hedef}`\n"
                        f"💰 Ref Bakiyesi   : `{u['ref']}`\n"
                        f"👥 Davet Ettiği   : `{u['ref_sayisi']}` kişi\n"
                        f"📅 Kayıt          : `{u['kayit_tarihi']}`\n"
                        f"🚫 Banlı          : {banlimi}\n"
                        f"🛒 Alışveriş      : `{len(gs)}`\n"
                        f"💸 Toplam Harcama : `{harcama}` Ref\n"
                        f"🏆 Sıralama       : `{sira}` / `{len(users)}`",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text("❌ Kullanıcı bulunamadı.")

            elif islem == "toplu":
                ok = 0
                fail = 0
                await update.message.reply_text("📣 Gönderiliyor, bekle...")
                for xid in list(users.keys()):
                    try:
                        await ctx.bot.send_message(
                            chat_id=xid,
                            text=f"📣 *Duyuru*\n\n{text}",
                            parse_mode="Markdown",
                        )
                        ok += 1
                        await asyncio.sleep(0.05)
                    except Exception:
                        fail += 1
                await update.message.reply_text(
                    f"📣 *Toplu Mesaj Tamamlandı*\n\n"
                    f"✅ Başarılı  : `{ok}`\n"
                    f"❌ Başarısız : `{fail}`\n"
                    f"📊 Toplam   : `{ok+fail}`",
                    parse_mode="Markdown",
                )

            elif islem == "transfer":
                await ref_transfer_isle(uid, text, update, ctx)
                return  # finally bloğu temizler

        except ValueError:
            await update.message.reply_text("❌ Hatalı format! Tekrar dene.")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
        finally:
            ctx.user_data.pop("islem", None)

    # ── Normal Kullanıcı Transfer İşlemi ─────────────────
    elif "islem" in ctx.user_data and ctx.user_data["islem"] == "transfer":
        await ref_transfer_isle(uid, text, update, ctx)
        ctx.user_data.pop("islem", None)


# ───────────────────────────────────────────────────────────────
# ÇALIŞTIR
# ───────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj))
    app.add_handler(CallbackQueryHandler(callback_handler))
    print(f"🤖 Wales Bot başlatıldı | Kanal: {KANAL_ADI}")
    app.run_polling()


if __name__ == "__main__":
    main()             
