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

@bot.tree.command(name="tam-yasak-kaldır", description="Belirtilen kullanıcının sunucudaki veya tüm Kara sunucularındaki yasağını kaldırır.")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(
    kullanici_id="Yasağı kaldırılacak kullanıcının Discord ID'si",
    secenek="Yasağın kaldırılacağı kapsamı seçin",
    sebep="Yasağın kaldırılma sebebi"
)
@app_commands.choices(secenek=[
    app_commands.Choice(name="Bu Sunucuda Yasağı Kaldır", value="bu_sunucu"),
    app_commands.Choice(name="Tüm Kara Sunucularından Yasak Kaldır", value="tum_kara")
])
async def tam_yasak_kaldir(interaction: discord.Interaction, kullanici_id: str, secenek: app_commands.Choice[str], sebep: str = "Sebep belirtilmedi"):
    await interaction.response.defer(ephemeral=False)
    
    # ID kontrolü
    try:
        user_id = int(kullanici_id)
        user = await bot.fetch_user(user_id)
    except ValueError:
        await interaction.followup.send("Geçersiz bir Kullanıcı ID'si girdiniz.")
        return
    except discord.NotFound:
        await interaction.followup.send("Bu ID'ye sahip bir Discord kullanıcısı bulunamadı.")
        return

    basarili_sunucular = []
    hatali_sunucular = []

    # 1. Bu Sunucuda Yasağı Kaldır
    if secenek.value == "bu_sunucu":
        try:
            await interaction.guild.unban(user, reason=f"{interaction.user} tarafından: {sebep}")
            basarili_sunucular.append(interaction.guild.name)
        except discord.NotFound:
            await interaction.followup.send("Bu kullanıcı mevcut sunucuda banlı değil.")
            return
        except discord.Forbidden:
            await interaction.followup.send("Bu sunucuda üyelerin yasağını kaldırmak için yeterli yetkim yok.")
            return

    # 2. Tüm Kara Sunucularından Yasak Kaldır
    elif secenek.value == "tum_kara":
        for guild in bot.guilds:
            try:
                await guild.unban(user, reason=f"[TÜM KARA UNBAN] {interaction.user} tarafından: {sebep}")
                basarili_sunucular.append(guild.name)
            except (discord.NotFound, discord.Forbidden):
                # Kullanıcı o sunucuda banlı değilse veya botun yetkisi yoksa atlar
                continue

    if not basarili_sunucular:
        await interaction.followup.send("Hiçbir sunucuda aktif ban bulunamadı veya yetki yetersiz.")
        return

    # Sunucu içi bildirim embed'i
    embed = discord.Embed(
        title="Yasak Kaldırma İşlemi Tamamlandı",
        color=discord.Color.green()
    )
    embed.add_field(name="Kullanıcı", value=f"{user.name} (`{user.id}`)", inline=False)
    embed.add_field(name="İşlemi Yapan Yetkili", value=f"{interaction.user.mention} ({interaction.user})", inline=False)
    embed.add_field(name="Kapsam", value=secenek.name, inline=False)
    embed.add_field(name="Kaldırılan Sunucular", value=", ".join(basarili_sunucular), inline=False)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    
    await interaction.followup.send(embed=embed)

    # Kullanıcıya DM Bildirimi (Yetkili Bilgisiyle)
    try:
        dm_embed = discord.Embed(
            title="Yasağınız Kaldırıldı",
            description=f"**{secenek.name}** kapsamında yasağınız kaldırılmıştır.",
            color=discord.Color.green()
        )
        dm_embed.add_field(name="Yasağı Kaldıran Yetkili", value=f"{interaction.user} ({interaction.user.display_name})", inline=False)
        dm_embed.add_field(name="Sebep", value=sebep, inline=False)
        dm_embed.set_footer(text="Aramıza tekrar hoş geldiniz.")
        
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.channel.send("Kullanıcının DM kutusu kapalı olduğu için özel bilgilendirme mesajı iletilemedi.")

# Yetki hatası yakalama
@tam_yasak_kaldir.error
async def tam_yasak_kaldir_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Bu komutu kullanmak için **Üyeleri Yasakla** yetkisine sahip olmalısın.", ephemeral=True)
        

