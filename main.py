import discord
from discord import app_commands
from discord.ext import commands
import os
from collections import defaultdict
import datetime

# 1. INTENTS AYARLARI (Koruma ve Modilasyon İçin Şarttır)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.moderation = True
intents.guilds = True

# ⚠️ BURAYA KENDİ SUNUCUNUZUN ID'SİNİ YAZIN (Sayısal olarak)
GUILD_ID = discord.Object(id=123456789012345678)

# -------------------------------------------------------------
# 2. TICKET SİSTEMİ (Persistent View)
# -------------------------------------------------------------
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

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

# -------------------------------------------------------------
# 3. KORUMA / SECURITY SİSTEMİ (LİMİTLİ ROL ÇEKME)
# -------------------------------------------------------------
class ModerationBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.action_limits = defaultdict(list)
        self.backup_roles = {}

    async def setup_hook(self):
        self.add_view(TicketView())

bot = ModerationBot()

# Limit Kontrolü (1 Dakikada 10 İşlem Limiti Aşıldığında Rol Çekilir)
async def check_and_punish(entry_user, guild, reason):
    now = datetime.datetime.now(datetime.timezone.utc)
    user_actions = bot.action_limits[entry_user.id]
    
    user_actions = [t for t in user_actions if (now - t).total_seconds() < 60]
    user_actions.append(now)
    bot.action_limits[entry_user.id] = user_actions

    if len(user_actions) >= 10:
        member = guild.get_member(entry_user.id)
        if member and not member.bot:
            user_roles = [role for role in member.roles if not role.is_default()]
            bot.backup_roles[member.id] = user_roles

            try:
                await member.remove_roles(*user_roles, reason=f"Güvenlik Limiti Aşıldı: {reason}")
                
                system_channel = guild.system_channel or next((c for c in guild.text_channels if "log" in c.name or "genel" in c.name), None)
                if system_channel:
                    embed = discord.Embed(
                        title="🚨 GÜVENLİK ALARMI (Limit Aşıldı)",
                        description=f"**{member.mention}** kısa sürede 10'dan fazla yetkili işlemi yaptığı için **bütün rolleri çekildi!**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Gerekçe", value=reason, inline=False)
                    embed.add_field(name="Geri Yükleme", value=f"`/rolleri_geri_ver kullanici:{member.id}` komutuyla roller iade edilebilir.", inline=False)
                    await system_channel.send(embed=embed)
            except discord.Forbidden:
                pass

@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if entry.target.id == user.id:
            await check_and_punish(entry.user, guild, "Seri Ban Atma")

@bot.event
async def on_member_remove(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        if entry.target.id == user.id:
            await check_and_punish(entry.user, guild, "Seri Kick Atma")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        await check_and_punish(entry.user, channel.guild, "Seri Kanal Silme")

# -------------------------------------------------------------
# 4. BOT BAŞLATMA & HATA ÖNLEYİCİ SENKRONİZASYON
# -------------------------------------------------------------
@bot.event
async def on_ready():
    try:
        # Eski çakışan komutları sunucudan tamamen siler
        bot.tree.clear_commands(guild=GUILD_ID)
        await bot.tree.sync(guild=GUILD_ID)
        
        # Güncel komut listesini doğrudan sunucuya işler
        bot.tree.copy_global_to(guild=GUILD_ID)
        synced = await bot.tree.sync(guild=GUILD_ID)
        
        print(f"✅ Bot {bot.user.name} aktif!")
        print(f"⚡ {len(synced)} adet Slash komutu sunucuya yüklendi.")
    except Exception as e:
        print(f"❌ Senkronizasyon Hatası: {e}")

# CommandNotFound ve Ağaç Hatalarını Yakalama (Konsol Çökmesini Engeller)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        await interaction.response.send_message("❌ Bu komut güncellendi veya önbellekte kalmış. Lütfen komut listenizi yenileyin.", ephemeral=True)
    else:
        print(f"⚠️ Komut Çalıştırma Hatası: {error}")

# -------------------------------------------------------------
# 5. TÜM SLASH KOMUTLARI
# -------------------------------------------------------------

# 1. /tam_yasak (Tüm Sunuculardan Banlama + DM Mesajı + Sunucu Listeleme)
@bot.tree.command(name="tam_yasak", description="Kullanıcıyı botun bulunduğu tüm sununculardan yasaklar.")
@app_commands.describe(kullanici="Yasaklanacak kullanıcı", sebep="Yasaklanma sebebi")
@app_commands.checks.has_permissions(ban_members=True)
async def tam_yasak(interaction: discord.Interaction, kullanici: discord.User, sebep: str = "Belirtilmedi"):
    await interaction.response.defer()

    # DM Bilgilendirmesi
    dm_sent = False
    try:
        dm_embed = discord.Embed(
            title="⛔ YASAKLANDINIZ",
            description="**Tüm Kara Kuvvetleri Sunucularından Yasaklandınız.**",
            color=discord.Color.dark_red()
        )
        dm_embed.add_field(name="Yasaklanma Sebebi", value=sebep, inline=False)
        await kullanici.send(embed=dm_embed)
        dm_sent = True
    except (discord.Forbidden, discord.HTTPException):
        dm_sent = False

    banned_guilds = []
    for guild in bot.guilds:
        try:
            await guild.ban(kullanici, reason=f"Tam Yasaklama ({interaction.user}): {sebep}")
            banned_guilds.append(guild.name)
        except (discord.Forbidden, discord.HTTPException):
            pass

    embed = discord.Embed(
        title="🔨 Tam Yasaklama İşlemi Tamamlandı",
        color=discord.Color.red()
    )
    embed.add_field(name="Hedef Kullanıcı", value=f"{kullanici.mention} ({kullanici.name})", inline=False)
    embed.add_field(name="DM Durumu", value="✅ DM Gönderildi" if dm_sent else "❌ DM Gönderilemedi (Kapalı)", inline=False)
    embed.add_field(name="Yasaklanma Sebebi", value=sebep, inline=False)
    
    if banned_guilds:
        guilds_str = "\n".join([f"• {g_name}" for g_name in banned_guilds])
        embed.add_field(name=f"✅ Yasaklandığı Sunucular ({len(banned_guilds)})", value=guilds_str, inline=False)
    else:
        embed.add_field(name="❌ Yasaklandığı Sunucular", value="Hiçbir sunucuda yetki uygulanamadı.", inline=False)

    await interaction.followup.send(embed=embed)


# 2. /tam_yasak_kaldir
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
        await interaction.followup.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send("❌ Botun yetkisi yetersiz.")


# 3. /ticket_kur
@bot.tree.command(name="ticket_kur", description="Bulunulan kanala Ticket oluşturma panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Destek Sistemi",
        description="Destek talebi oluşturmak için aşağıdaki **'Destek Bileti Aç'** butonuna tıklayın.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message("✅ Ticket paneli kuruldu.", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketView())


# 4. /rol_ver (ErensiBot Özelliği)
@bot.tree.command(name="rol_ver", description="Belirtilen kullanıcıya rol verir.")
@app_commands.describe(kullanici="Rol verilecek üye", rol="Verilecek rol")
@app_commands.checks.has_permissions(manage_roles=True)
async def rol_ver(interaction: discord.Interaction, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.add_roles(rol)
        await interaction.response.send_message(f"✅ {kullanici.mention} kullanıcısına {rol.mention} rolü başarıyla verildi.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Botun rol sırası yetersiz.", ephemeral=True)


# 5. /rol_al (ErensiBot Özelliği)
@bot.tree.command(name="rol_al", description="Belirtilen kullanıcıdan rol alır.")
@app_commands.describe(kullanici="Rol alınacak üye", rol="Alınacak rol")
@app_commands.checks.has_permissions(manage_roles=True)
async def rol_al(interaction: discord.Interaction, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.remove_roles(rol)
        await interaction.response.send_message(f"✅ {kullanici.mention} kullanıcısından {rol.mention} rolü alındı.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Botun rol sırası yetersiz.", ephemeral=True)


# 6. /rolleri_geri_ver (Güvenlik Tarafından Çekilen Rolleri İade Eder)
@bot.tree.command(name="rolleri_geri_ver", description="Güvenlik sistemi tarafından tüm rolleri alınan yetkiliye rollerini iade eder.")
@app_commands.describe(kullanici="Rolleri geri verilecek üye")
@app_commands.checks.has_permissions(administrator=True)
async def rolleri_geri_ver(interaction: discord.Interaction, kullanici: discord.Member):
    roles_to_restore = bot.backup_roles.get(kullanici.id)

    if not roles_to_restore:
        await interaction.response.send_message(f"❌ {kullanici.mention} kullanıcısına ait sistemde yedeklenmiş rol bulunamadı.", ephemeral=True)
        return

    try:
        await kullanici.add_roles(*roles_to_restore, reason="Yönetici Tarafından Rol İadesi Yapıldı")
        del bot.backup_roles[kullanici.id]
        await interaction.response.send_message(f"✅ {kullanici.mention} kullanıcısının çekilen **tüm rolleri başarıyla geri verildi!**")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Yetki hatası. Botun en üst role sahip olduğundan emin olun.", ephemeral=True)


# 7. /dm (Direkt Mesaj Gönderme)
@bot.tree.command(name="dm", description="Belirtilen kullanıcıya özel mesaj (DM) gönderir.")
@app_commands.describe(kullanici="Mesaj gönderilecek kullanıcı", mesaj="Gönderilecek mesaj")
@app_commands.checks.has_permissions(administrator=True)
async def dm(interaction: discord.Interaction, kullanici: discord.User, mesaj: str):
    try:
        await kullanici.send(f"📩 **Yetkili Mesajı:** {mesaj}")
        await interaction.response.send_message(f"✅ {kullanici.mention} kullanıcısına DM gönderildi.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Kullanıcının DM kutusu kapalı olduğu için mesaj gönderilemedi.", ephemeral=True)

# -------------------------------------------------------------
# 6. RENDER GİZLİ (MASKELENMİŞ) TOKEN OKUYUCU
# -------------------------------------------------------------
TOKEN = (
    os.getenv("TOKEN") or 
    os.getenv("DISCORD_TOKEN") or 
    os.getenv("BOT_TOKEN") or 
    os.getenv("MASKED_TOKEN")
)

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ HATA: Render ortam değişkenlerinde (Environment Variables) token bulunamadı!")
    
