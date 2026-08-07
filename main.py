from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
import datetime

# --- BULUT SUNUCU İÇİN CANLI TUTMA KODU (FLASK) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot 7/24 Aktif!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# --------------------------------------------------

# --- BOT KURULUMU VE INTENT AYARLARI ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komutları senkronize edildi.")

bot = MyBot()

# --- TICKET BOTOON VE BİLET SİSTEMİ VIEW ---
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Aç 📩", style=discord.ButtonStyle.primary, custom_id="ticket_open_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_role = discord.utils.get(guild.roles, name="Yetkili") 
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{member.name}"
        
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"Zaten açık bir biletiniz var: {existing_channel.mention}", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        await interaction.response.send_message(f"Ticket kanalınız oluşturuldu: {ticket_channel.mention}", ephemeral=True)
        await ticket_channel.send(f"Merhaba {member.mention}, yetkililer en kısa sürede ilgilenecektir. Talebinizi yazabilirsiniz.")

# --- BOTA GİRİŞ EVENT'İ ---
@bot.event
async def on_ready():
    print(f"{bot.user} aktif ve hazır!")

# --- 1. KOMUT: /tam_yasakla ---
@bot.tree.command(name="tam_yasakla", description="Belirtilen kullanıcıyı botun ekli olduğu tüm Kara Kuvvetleri sunucularından banlar.")
@app_commands.checks.has_permissions(ban_members=True)
async def tam_yasakla(interaction: discord.Interaction, kullanici: discord.User, sebep: str = "Kara Kuvvetleri Ortak Yasaklaması"):
    await interaction.response.defer(ephemeral=True)
    banlanan_sunucular, hata_sunuculari = [], []

    embed_dm = discord.Embed(
        title="⚠️ Sunuculardan Yasaklandınız",
        description=f"**Yasaklandığınız Sunucu:** {interaction.guild.name}\n**Yasaklanma Sebebi:** {sebep}",
        color=discord.Color.red()
    )
    embed_dm.set_footer(text=f"İşlemi Yapan Yetkili: {interaction.user}")

    try: await kullanici.send(embed=embed_dm)
    except Exception: pass

    for guild in bot.guilds:
        try:
            await guild.ban(kullanici, reason=f"{interaction.user} tarafından: {sebep}")
            banlanan_sunucular.append(guild.name)
        except Exception:
            hata_sunuculari.append(guild.name)

    mesaj = f"**{kullanici.tag}** kullanıcısına bildirim gönderildi ve **{len(banlanan_sunucular)}** sunucudan yasaklandı.\n"
    if banlanan_sunucular: mesaj += f"\n✅ **Yasaklandığı Sunucular:** {', '.join(banlanan_sunucular)}"
    if hata_sunuculari: mesaj += f"\n❌ **Yasaklanamadığı Sunucular:** {', '.join(hata_sunuculari)}"

    await interaction.followup.send(mesaj, ephemeral=True)

# --- 2. KOMUT: /dm ---
@bot.tree.command(name="dm", description="Belirtilen kullanıcıya bot üzerinden DM mesajı, görsel veya bağlantı gönderir.")
@app_commands.checks.has_permissions(administrator=True)
async def dm(
    interaction: discord.Interaction, 
    kullanici: discord.User, 
    mesaj: str, 
    gorsel_url: str = None, 
    buton_etiket: str = None, 
    buton_url: str = None
):
    embed = discord.Embed(title="📢 Tarafınıza Bir Mesaj Var", description=mesaj, color=discord.Color.blue())
    embed.set_footer(text=f"Gönderen Sunucu: {interaction.guild.name}")

    if gorsel_url: embed.set_image(url=gorsel_url)

    view = None
    if buton_etiket and buton_url:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=buton_etiket, url=buton_url))

    try:
        await kullanici.send(embed=embed, view=view)
        await interaction.response.send_message(f"{kullanici.mention} kullanıcısına DM başarıyla gönderildi.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Kullanıcının DM' kutusu kapalı olduğu için mesaj gönderilemedi.", ephemeral=True)

# --- 3. KOMUT: /mute ---
@bot.tree.command(name="mute", description="Belirtilen kullanıcıyı belirli bir süre boyunca sunucuda susturur (Timeout).")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, üye: discord.Member, dakika: int, sebep: str = "Belirtilmedi"):
    sure = datetime.timedelta(minutes=dakika)
    embed_dm = discord.Embed(
        title="🔇 Sunucuda Susturuldunuz",
        description=f"**Susturulduğunuz Sunucu:** {interaction.guild.name}\n**Süre:** {dakika} Dakika\n**Sebep:** {sebep}",
        color=discord.Color.orange()
    )
    embed_dm.set_footer(text=f"İşlemi Yapan Yetkili: {interaction.user}")

    try: await üye.send(embed=embed_dm)
    except Exception: pass

    try:
        await üye.timeout(sure, reason=f"{interaction.user} tarafından: {sebep}")
        await interaction.response.send_message(f"🚫 {üye.mention}, **{dakika} dakika** boyunca susturuldu.\n**Sebep:** *{sebep}*")
    except Exception:
        await interaction.response.send_message("Kullanıcı susturulamadı. Bot yetkisini kontrol edin.", ephemeral=True)

# --- 4. KOMUT: /ticket_kur ---
@bot.tree.command(name="ticket_kur", description="Etiketlenen kanala Ticket oluşturma panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction, kanal: discord.TextChannel):
    embed = discord.Embed(
        title="🎫 Destek Sistemi",
        description="Yetkili ekibimizle iletişime geçmek ve destek almak için aşağıdaki **Ticket Aç** butonuna tıklayınız.",
        color=discord.Color.green()
    )
    await kanal.send(embed=embed, view=TicketButton())
    await interaction.response.send_message(f"Ticket paneli {kanal.mention} kanalına kuruldu.", ephemeral=True)

# --- BAŞLATMA ---
keep_alive() # Web sunucusunu başlatır
import os

# ... bot kodunun geri kalanı ...

import os

bot.run(os.environ['DISCORD_TOKEN'])
import discord
from discord import app_commands
from discord.ext import commands
import os

# 1. INTENTS AYARLARI
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 2. TICKET BUTONU VE SİSTEMİ (Persistent View)
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Bot yeniden başlasa da butonlar aktif kalır

    @discord.ui.button(label="🎫 Destek Bileti Aç", style=discord.ButtonStyle.green, custom_id="open_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        channel_name = f"ticket-{user.name.lower()}"
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if existing_channel:
            await interaction.response.send_message(f"❌ Zaten açık bir biletiniz var: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        try:
            channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
            await interaction.response.send_message(f"✅ Biletiniz oluşturuldu: {channel.mention}", ephemeral=True)
            
            embed = discord.Embed(
                title="🎫 Destek Bileti",
                description=f"Merhaba {user.mention}, yetkililer en kısa sürede ilgilenecektir. Talebinizi yazabilirsiniz.",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Botun kanal oluşturma yetkisi yetersiz!", ephemeral=True)


# 3. BOT SINIFI
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Persistent butonları hafızaya yükler
        self.add_view(TicketView())

bot = MyBot()


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot {bot.user.name} olarak giriş yaptı!")
        print(f"⚡ {len(synced)} adet Slash komutu başarıyla senkronize edildi.")
    except Exception as e:
        print(f"❌ Senkronizasyon hatası: {e}")


# 4. KOMUT 1: /tam_yasak_kaldir
@bot.tree.command(name="tam_yasak_kaldir", description="Belirtilen kullanıcının yasağını kaldırır.")
@app_commands.describe(kullanici="Yasağı kaldırılacak kullanıcının ID'si veya Kullanıcı Adı")
@app_commands.checks.has_permissions(ban_members=True)
async def tam_yasak_kaldir(interaction: discord.Interaction, kullanici: str):
    await interaction.response.defer()

    banned_users = [entry async for entry in interaction.guild.bans()]
    target_user = None

    for ban_entry in banned_users:
        user = ban_entry.user
        if kullanici in (str(user.id), user.name, f"{user.name}#{user.discriminator}"):
            target_user = user
            break

    if target_user is None:
        await interaction.followup.send(f"❌ `{kullanici}` adlı kullanıcı banlılar listesinde bulunamadı.")
        return

    try:
        await interaction.guild.unban(target_user)
        
        embed = discord.Embed(title="🔓 Yasak Kaldırıldı", color=discord.Color.green())
        embed.add_field(name="Kullanıcı", value=f"{target_user.mention} ({target_user.name})", inline=True)
        embed.add_field(name="ID", value=f"`{target_user.id}`", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        embed.set_thumbnail(url=target_user.display_avatar.url)

        await interaction.followup.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send("❌ Botun bu işlem için yetkisi yetersiz.")


# 5. KOMUT 2: /ticket_kur
@bot.tree.command(name="ticket_kur", description="Etiketlenen veya bulunulan kanala Ticket oluşturma panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Destek Sistemi",
        description="Destek talebi oluşturmak için aşağıdaki **'Destek Bileti Aç'** butonuna tıklayın.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message("✅ Ticket paneli kuruldu.", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketView())


# 6. RENDER MASKELENMİŞ TOKEN OKUMA (RENDER ENVIRONMENT VARIABLES)
# Render üzerinde maskelediğiniz değişkene hangi ismi verdiyseniz otomatik algılar
TOKEN = (
    os.getenv("TOKEN") or 
    os.getenv("DISCORD_TOKEN") or 
    os.getenv("BOT_TOKEN") or 
    os.getenv("MASKED_TOKEN")
)

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ HATA: Render Environment Variables kısmında maskelenmiş bot tokeni bulunamadı!")
            
