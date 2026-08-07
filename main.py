import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta

TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BAN_FILE = "banlilar.txt"
WARN_FILE = "warns.txt"

def get_banlilar():
    if not os.path.exists(BAN_FILE): return set()
    with open(BAN_FILE, "r") as f:
        return set(line.strip() for line in f.readlines() if line.strip())

def save_banlilar(banlilar):
    with open(BAN_FILE, "w") as f:
        for uid in banlilar:
            f.write(f"{uid}\n")

# Basit uyarı veri tabanı (KullaniciID: UyariSayisi)
def get_warns():
    warns = {}
    if not os.path.exists(WARN_FILE): return warns
    with open(WARN_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 2:
                warns[int(parts[0])] = int(parts[1])
    return warns

def save_warns(warns):
    with open(WARN_FILE, "w") as f:
        for uid, count in warns.items():
            f.write(f"{uid}:{count}\n")

whitelist_ids = set()
alinan_roller = {}

def whitelist_kontrol(interaction: discord.Interaction) -> bool:
    return interaction.user.id == interaction.guild.owner_id or interaction.user.id in whitelist_ids

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} komut senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print(f"Bot Hazır: {bot.user}")

# ==========================================
# GÜVENLİK 1: Manuel Banı Engelleme
# ==========================================
@bot.event
async def on_member_unban(guild, user):
    banlilar = get_banlilar()
    if str(user.id) in banlilar:
        try:
            await guild.ban(user, reason="Kalıcı Güvenlik: Bot banı manuel kaldırılamaz!")
        except Exception:
            pass

# ==========================================
# GÜVENLİK 2: İzinsiz Yönetici Rolü Verilmesini Engelleme
# ==========================================
@bot.event
async def on_member_update(before, after):
    if len(after.roles) > len(before.roles):
        new_role = next((role for role in after.roles if role not in before.roles), None)
        if new_role and new_role.permissions.administrator and not after.guild_owner:
            try:
                await after.edit(roles=[r for r in before.roles], reason="GÜVENLİK: İzinsiz Yönetici yetkisi engellendi!")
                for channel in after.guild.text_channels:
                    if "log" in channel.name or "güvenlik" in channel.name:
                        embed = discord.Embed(
                            title="🚨 İZİNSİZ YÖNETİCİ ENGellENDİ",
                            description=f"**{after}** adlı kullanıcıya izinsiz Yönetici yetkisi verildiği için yetki geri alındı.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                        break
            except Exception:
                pass

# ==========================================
# 1. WHITELIST KOMUTLARI
# ==========================================
@bot.tree.command(name="whitelist-ekle", description="Beyaz listeye kullanıcı ekler.")
async def whitelist_ekle(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return
    
    whitelist_ids.add(member.id)
    await interaction.response.send_message(f"Başarıyla **{member.mention}** beyaz listeye eklendi.", ephemeral=True)

@bot.tree.command(name="whitelist-cikar", description="Beyaz listeden kullanıcı çıkarır.")
async def whitelist_cikar(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return

    if member.id in whitelist_ids:
        whitelist_ids.remove(member.id)
        await interaction.response.send_message(f"**{member.mention}** beyaz listeden çıkarıldı.", ephemeral=True)
    else:
        await interaction.response.send_message("Bu kullanıcı zaten listede yok.", ephemeral=True)

@bot.tree.command(name="whitelist-liste", description="Beyaz listedeki kişileri gösterir.")
async def whitelist_liste(interaction: discord.Interaction):
    if not whitelist_ids:
        await interaction.response.send_message("Beyaz listede henüz kimse yok.", ephemeral=True)
        return
    
    uyeler = ", ".join([f"<@{uid}>" for uid in whitelist_ids])
    embed = discord.Embed(title="📋 Bot Whitelist Listesi", description=uyeler, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================
# 2. /duyuru KOMUTU (Rol veya Etiket Destekli)
# ==========================================
@bot.tree.command(name="duyuru", description="Belirtilen kanala @everyone, @here veya özel bir rol etiketleyerek duyuru atar.")
async def duyuru(interaction: discord.Interaction, kanal: discord.TextChannel, secim: str, baslik: str, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    embed = discord.Embed(title=f"📢 {baslik}", description=mesaj, color=discord.Color.gold())
    embed.set_footer(text=f"Yetkili: {interaction.user}", icon_url=interaction.user.display_avatar.url)

    ping_metni = ""
    if secim.lower() == "@everyone":
        ping_metni = "@everyone"
    elif secim.lower() == "@here":
        ping_metni = "@here"
    else:
        # Eğer rol ismi veya ID yazıldıysa bulmaya çalışalım
        role = discord.utils.get(interaction.guild.roles, name=secim)
        if not role:
            try:
                role = interaction.guild.get_role(int(secim))
            except ValueError:
                pass
        
        if role:
            ping_metni = role.mention
        else:
            ping_metni = secim # Bulunamazsa direkt metin olarak bırakır

    try:
        await kanal.send(content=ping_metni, embed=embed)
        await interaction.response.send_message(f"Duyuru başarıyla {kanal.mention} kanalına gönderildi.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Duyuru gönderilirken hata oluştu: {e}", ephemeral=True)

# ==========================================
# 3. /sil KOMUTU (Mesaj Silme)
# ==========================================
@bot.tree.command(name="sil", description="Belirtilen miktarda mesajı siler.")
async def sil(interaction: discord.Interaction, adet: int):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    if adet < 1:
        await interaction.response.send_message("Lütfen 1'den büyük bir sayı girin.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        silinenler = await interaction.channel.purge(limit=adet)
        await interaction.followup.send(f"Başarıyla **{len(silinenler)}** adet mesaj silindi.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Mesajlar silinirken hata oluştu: {e}", ephemeral=True)

# ==========================================
# 4. /uyar KOMUTU (3. Uyarıda Oto-Mute)
# ==========================================
@bot.tree.command(name="uyar", description="Kullanıcıyı uyarır. 3. uyarıda otomatik mute atar.")
async def uyar(interaction: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    warns = get_warns()
    user_id = member.id
    warns[user_id] = warns.get(user_id, 0) + 1
    current_warns = warns[user_id]
    save_warns(warns)

    # Kullanıcıya DM bildirimi gönder
    try:
        dm_embed = discord.Embed(
            title="⚠️ Uyarı Aldınız!",
            description=f"**{interaction.guild.name}** sunucusunda **{interaction.user}** tarafından uyarıldınız.",
            color=discord.Color.yellow()
        )
        dm_embed.add_field(name="Sebep", value=sebep, inline=False)
        dm_embed.add_field(name="Toplam Uyarı Sayınız", value=str(current_warns), inline=False)
        await member.send(embed=dm_embed)
    except Exception:
        pass

    ceza_mesaji = f"{member.mention} başarıyla uyarıldı. (Toplam Uyarı: {current_warns})"

    # 3. Uyarıda Otomatik Mute (Örn: 30 Dakika)
    if current_warns >= 3:
        try:
            durum_suresi = timedelta(minutes=30)
            await member.timeout(durum_suresi, reason="3 kez uyarı sınırına ulaşıldı.")
            warns[user_id] = 0 # Uyarıları sıfırla
            save_warns(warns)
            ceza_mesaji += f"\n🚨 Kullanıcı 3 uyarı sınırını aştığı için **30 dakika** süreyle susturuldu (mute)!"
        except Exception as e:
            ceza_mesaji += f"\n(Ancak otomatik mute atılamadı: {e})"

    embed = discord.Embed(title="⚠️ Kullanıcı Uyarıldı", description=ceza_mesaji, color=discord.Color.orange())
    embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
    embed.add_field(name="Sebep", value=sebep, inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================
# 5. /tamyasak KOMUTU
# ==========================================
class TamYasakSelect(discord.ui.Select):
    def __init__(self, member, sebep):
        self.member = member
        self.sebep = sebep
        options = [
            discord.SelectOption(label="Sadece Bu Sunucudan Yasakla", value="tek", description="Yasaklama yalnızca bu sunucuda uygulanır."),
            discord.SelectOption(label="Tüm Sunuculardan Yasakla", value="tum", description="Botun bulunduğu tüm ortak sunuculardan yasaklanır.")
        ]
        super().__init__(placeholder="Yasaklama kapsamını seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        secim = self.values[0]
        yasaklanan_yerler = []
        
        banlilar = get_banlilar()
        banlilar.add(str(self.member.id))
        save_banlilar(banlilar)

        if secim == "tek":
            try:
                await interaction.guild.ban(self.member, reason=f"Tekil Yasak - Yetkili: {interaction.user} | Sebep: {self.sebep}")
                yasaklanan_yerler.append(interaction.guild.name)
            except Exception:
                await interaction.followup.send("Kullanıcı bu sunucudan yasaklanamadı.", ephemeral=True)
                return
        elif secim == "tum":
            for guild in bot.guilds:
                try:
                    await guild.ban(self.member, reason=f"Tam Yasak - Yetkili: {interaction.user} | Sebep: {self.sebep}")
                    yasaklanan_yerler.append(guild.name)
                except Exception:
                    continue

        embed = discord.Embed(title="🚨 Yasaklama İşlemi Tamamlandı", color=discord.Color.dark_red())
        embed.add_field(name="Hedef Kullanıcı", value=f"{self.member} (`{self.member.id}`)", inline=False)
        embed.add_field(name="İşlemi Yapan", value=interaction.user.mention, inline=False)
        embed.add_field(name="Sebep", value=self.sebep, inline=False)
        embed.add_field(name="İşlem Yapılan Sunucular", value=", ".join(yasaklanan_yerler), inline=False)
        
        await interaction.followup.send(embed=embed)

class TamYasakView(discord.ui.View):
    def __init__(self, member, sebep):
        super().__init__(timeout=60)
        self.add_item(TamYasakSelect(member, sebep))

@bot.tree.command(name="tamyasak", description="Kullanıcıyı seçmeli olarak yasaklar.")
async def tamyasak(interaction: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    view = TamYasakView(member, sebep)
    embed = discord.Embed(title="⚠️ Yasaklama Kapsamı Seçimi", description=f"**{member}** için yasaklama türünü seçiniz.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==========================================
# 6. /tamyasakkaldir KOMUTU
# ==========================================
class UnbanSelect(discord.ui.Select):
    def __init__(self, target_user):
        self.target_user = target_user
        options = [
            discord.SelectOption(label="Bu Sunucudan Kaldır", value="tek", description="Yasağı tamamen kaldırır."),
            discord.SelectOption(label="Tüm Sunuculardan Kaldır", value="tum_kara", description="Tüm sunuculardaki yasakları kaldırır.")
        ]
        super().__init__(placeholder="Yasağın kaldırılacağı kapsamı seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        secim = self.values[0]
        
        banlilar = get_banlilar()
        if str(self.target_user.id) in banlilar:
            banlilar.remove(str(self.target_user.id))
            save_banlilar(banlilar)

        if secim == "tek":
            try:
                await interaction.guild.unban(self.target_user, reason=f"Yetkili: {interaction.user}")
            except Exception:
                await interaction.followup.send("Bu sunucuda yasak kaldırılamadı.", ephemeral=True)
                return
        elif secim == "tum_kara":
            for guild in bot.guilds:
                try:
                    await guild.unban(self.target_user, reason=f"Genel Af - Yetkili: {interaction.user}")
                except Exception:
                    continue

        embed = discord.Embed(title="✅ Yasak Kaldırma İşlemi Başarılı", color=discord.Color.green())
        embed.add_field(name="Kullanıcı", value=f"{self.target_user} (`{self.target_user.id}`)", inline=False)
        embed.add_field(name="İşlemi Yapan", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

class UnbanView(discord.ui.View):
    def __init__(self, target_user):
        super().__init__(timeout=60)
        self.add_item(UnbanSelect(target_user))

@bot.tree.command(name="tamyasakkaldir", description="Yasağı kalıcı olarak kaldırır.")
async def tamyasakkaldir(interaction: discord.Interaction, user_id: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    try:
        user = await bot.fetch_user(int(user_id))
    except Exception:
        await interaction.response.send_message("Geçerli bir kullanıcı ID'si giriniz.", ephemeral=True)
        return

    view = UnbanView(user)
    embed = discord.Embed(title="🔓 Yasak Kaldırma Yönetimi", description=f"**{user}** için kapsam seçiniz.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==========================================
# 7. /mute KOMUTU (Sebepli DM Bildirimli)
# ==========================================
@bot.tree.command(name="mute", description="Kullanıcıya sebep ve bildirimli zaman aşımı uygular.")
async def mute(interaction: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    durum_suresi = timedelta(minutes=dakika)
    try:
        await member.timeout(durum_suresi, reason=sebep)
        
        # Kullanıcıya DM ile sebep bildirimi gönder
        try:
            dm_embed = discord.Embed(title="🔇 Susturuldunuz (Mute)", color=discord.Color.red())
            dm_embed.add_field(name="Sunucu", value=interaction.guild.name, inline=False)
            dm_embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
            dm_embed.add_field(name="Sebep", value=sebep, inline=False)
            await member.send(embed=dm_embed)
        except Exception:
            pass

        embed = discord.Embed(title="🔇 Kullanıcı Susturuldu", color=discord.Color.orange())
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Mute atılırken hata oluştu: {e}", ephemeral=True)

# ==========================================
# 8. TICKET SİSTEMİ
# ==========================================
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Destek Talebi Aç 🎫", style=discord.ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="DESTEK TALEPLERI")
        if not category:
            category = await guild.create_category("DESTEK TALEPLERI")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(f"destek-{interaction.user.name}", category=category, overwrites=overwrites)
        
        embed = discord.Embed(
            title="Destek Talebi Oluşturuldu", 
            description="Yetkililer kısa süre içinde ilgilenecektir.", 
            color=discord.Color.gold()
        )
        
        await channel.send(f"@here {interaction.user.mention}", embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"Destek kanalınız oluşturuldu: {channel.mention}", ephemeral=True)

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Sahiplen 🙋‍♂️", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        embed = discord.Embed(
            title="🙋‍♂️ Talep Sahiplenildi", 
            description=f"Bu destek talebi **{interaction.user.mention}** tarafından sahiplenildi.", 
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Talebi Kapat 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Destek talebi kapatılıyor, kanal 3 saniye içinde silinecektir...")
        await asyncio.sleep(3)
        await interactio
