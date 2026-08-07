import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta

# Token'ı Railway panelindeki 'DISCORD_TOKEN' değişkeninden çeker
TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Botun güvenlik amaçlı çektiği rolleri saklamak için geçici sözlük
alinan_roller = {}

# Bot tarafından banlanan ve mute atılan kullanıcıların ID listeleri (Manuel açılmayı engellemek için)
bot_tarafindan_banlilar = set()
bot_tarafindan_muteliler = set()

# Whitelist (Erişim izni olan kullanıcı ID'leri) - Başlangıçta boş kalabilir veya ID eklenebilir
whitelist_ids = set()

# Whitelist Kontrol Fonksiyonu
def whitelist_kontrol(interaction: discord.Interaction) -> bool:
    # Sunucu sahibi veya whitelist'e eklenenler erişebilir
    return interaction.user.id == interaction.guild.owner_id or interaction.user.id in whitelist_ids


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} adet slash (/) komutu senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print(f"Bot Başarıyla Giriş Yaptı: {bot.user}")


# ==========================================
# GÜVENLİK 1: İzinsiz Yönetici Koruması
# ==========================================
@bot.event
async def on_member_update(before, after):
    if len(after.roles) > len(before.roles):
        new_role = next((role for role in after.roles if role not in before.roles), None)
        if new_role and new_role.permissions.administrator and not after.guild_owner:
            alinan_roller[after.id] = [r for r in after.roles if r != after.guild.default_role]
            await after.edit(roles=[after.guild.default_role], reason="GÜVENLİK: İzinsiz Yönetici yetkisi tespit edildi!")
            
            for channel in after.guild.text_channels:
                if "log" in channel.name or "güvenlik" in channel.name:
                    embed = discord.Embed(
                        title="🚨 GÜVENLİK KORUMA DEVREYE GİRDİ",
                        description=f"**{after}** adlı kişiye izinsiz Yönetici yetkisi verilmeye çalışıldığı için tüm rolleri alındı.",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="Rolleri geri vermek için: /rollerigeri komutunu kullanın.")
                    await channel.send(embed=embed)
                    break


# ==========================================
# GÜVENLİK 2: Manuel Ban Açılmasını Engelleme (Anti-Unban)
# ==========================================
@bot.event
async def on_member_unban(guild, user):
    if user.id in bot_tarafindan_banlilar:
        try:
            await guild.ban(user, reason="Kalıcı Güvenlik Koruması: Bot banı manuel olarak kaldırılamaz!")
        except Exception:
            pass


# ==========================================
# GÜVENLİK 3: Manuel Mute (Timeout) Açılmasını Engelleme
# ==========================================
@bot.event
async def on_member_update(before, after):
    # Yönetici kontrolü mantığı (Yukarıdakini korumak için birleştirildi)
    if len(after.roles) > len(before.roles):
        new_role = next((role for role in after.roles if role not in before.roles), None)
        if new_role and new_role.permissions.administrator and not after.guild_owner:
            alinan_roller[after.id] = [r for r in after.roles if r != after.guild.default_role]
            await after.edit(roles=[after.guild.default_role], reason="GÜVENLİK: İzinsiz Yönetici yetkisi tespit edildi!")
            
            for channel in after.guild.text_channels:
                if "log" in channel.name or "güvenlik" in channel.name:
                    embed = discord.Embed(
                        title="🚨 GÜVENLİK KORUMA DEVREYE GİRDİ",
                        description=f"**{after}** adlı kişiye izinsiz Yönetici yetkisi verilmeye çalışıldığı için tüm rolleri alındı.",
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed)
                    break

    # Mute kalkma kontrolü
    if before.is_timed_out() and not after.is_timed_out():
        if after.id in bot_tarafindan_muteliler:
            try:
                await after.timeout(timedelta(hours=24), reason="Kalıcı Güvenlik Koruması: Bot mutesi manuel kaldırılamaz!")
            except Exception:
                pass


# ==========================================
# DM BİLDİRİM YARDIMCISI
# ==========================================
async def bildirim_gonder(member, islem, sebep):
    try:
        embed = discord.Embed(title="🛡️ Moderasyon Bildirimi", color=discord.Color.orange())
        embed.add_field(name="Yapılan İşlem", value=islem, inline=False)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await member.send(embed=embed)
    except Exception:
        pass


# ==========================================
# 1. /whitelist KOMUTLARI (Bota Kimlerin Erişebileceği)
# ==========================================
@bot.tree.group(name="whitelist", description="Bot erişim beyaz liste yönetimi.")
@app_commands.checks.has_permissions(administrator=True)
async def whitelist(interaction: discord.Interaction):
    pass

@whitelist.command(name="ekle", description="Bir kullanıcıya bot komutlarını kullanma yetkisi verir.")
async def whitelist_ekle(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return
    
    whitelist_ids.add(member.id)
    await interaction.response.send_message(f"Başarıyla **{member.mention}** beyaz listeye (whitelist) eklendi.", ephemeral=True)

@whitelist.command(name="cikar", description="Bir kullanıcının bot erişim yetkisini alır.")
async def whitelist_cikar(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return

    if member.id in whitelist_ids:
        whitelist_ids.remove(member.id)
        await interaction.response.send_message(f"**{member.mention}** beyaz listeden çıkarıldı.", ephemeral=True)
    else:
        await interaction.response.send_message("Bu kullanıcı zaten listede yok.", ephemeral=True)

@whitelist.command(name="liste", description="Beyaz listedeki kişileri gösterir.")
async def whitelist_liste(interaction: discord.Interaction):
    if not whitelist_ids:
        await interaction.response.send_message("Beyaz listede henüz kimse yok.", ephemeral=True)
        return
    
    uyeler = ", ".join([f"<@{uid}>" for uid in whitelist_ids])
    embed = discord.Embed(title="📋 Bot Whitelist Listesi", description=uyeler, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==========================================
# 2. /tamyasak KOMUTU (Seçmeli & Kalıcı)
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
        bot_tarafindan_banlilar.add(self.member.id)

        if secim == "tek":
            try:
                await bildirim_gonder(self.member, f"{interaction.guild.name} Sunucusundan Yasaklandınız", self.sebep)
                await interaction.guild.ban(self.member, reason=f"Tekil Yasak - Yetkili: {interaction.user} | Sebep: {self.sebep}")
                yasaklanan_yerler.append(interaction.guild.name)
            except Exception:
                await interaction.followup.send("Kullanıcı bu sunucudan yasaklanamadı.", ephemeral=True)
                return
        elif secim == "tum":
            for guild in bot.guilds:
                try:
                    await bildirim_gonder(self.member, f"Tüm Sunuculardan Yasaklandınız", self.sebep)
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
# 3. /tamyasakkaldir KOMUTU (Bot Listesinden Çıkararak Kaldırma)
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
        basarili_sunucular = []
        
        # Bot koruma listesinden çıkarıyoruz ki manuel sanıp tekrar atmasın
        if self.target_user.id in bot_tarafindan_banlilar:
            bot_tarafindan_banlilar.remove(self.target_user.id)

        if secim == "tek":
            try:
                await interaction.guild.unban(self.target_user, reason=f"Yetkili: {interaction.user}")
                basarili_sunucular.append(interaction.guild.name)
            except Exception:
                await interaction.followup.send("Bu sunucuda yasak kaldırılamadı.", ephemeral=True)
                return
        elif secim == "tum_kara":
            for guild in bot.guilds:
                try:
                    await guild.unban(self.target_user, reason=f"Genel Af - Yetkili: {interaction.user}")
                    basarili_sunucular.append(guild.name)
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
# 4. /mute KOMUTU (Kalıcı / Manuel Açılamaz)
# ==========================================
@bot.tree.command(name="mute", description="Kullanıcıya bot korumalı zaman aşımı uygular.")
async def mute(interaction: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    durum_suresi = timedelta(minutes=dakika)
    try:
        bot_tarafindan_muteliler.add(member.id)
        await member.timeout(durum_suresi, reason=sebep)
        await bildirim_gonder(member, f"{interaction.guild.name} Sunucusunda Mutelediniz", sebep)
        
        embed = discord.Embed(title="🔇 Kullanıcı Muteleendi", color=discord.Color.orange())
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Mute atılırken hata oluştu: {e}", ephemeral=True)


# ==========================================
# 5. /ticket-olustur KOMUTU
# ==========================================
class TicketCreateView(discord.ui.View):
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
        
        embed = discord.Embed(title="Destek Talebi Oluşturuldu", description="Yetkililer kısa süre içinde ilgilenecektir.", color=discord.Color.gold())
        view = TicketCloseView()
        
        await channel.send(f"@here {interaction.user.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"Destek kanalınız oluşturuldu: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Kapat 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Destek talebi kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-olustur", description="Destek paneli kurar.")
async def ticket_olustur(interaction: discord.Interaction):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    embed = discord.Embed(title="🎫 Destek Sistemi", description="Talep açmak için butona tıklayın.", color=discord.Color.blurple())
    view = TicketCreateView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Destek paneli kuruldu.", ephemeral=True)


# ==========================================
# 6. /dm KOMUTU
# ==========================================
@bot.tree.command(name="dm", description="Özel mesaj gönderir.")
async def dm(interaction: discord.Interaction, member: discord.Member, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    try:
        embed = discord.Embed(title="📬 Yetkili Mesajı", description=mesaj, color=discord.Color.orange())
        await member.send(embed=embed)
        await interaction.response.send_message(f"Başarıyla DM gönderildi.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Kullanıcının DM kutusu kapalı.", ephemeral=True)


# ==========================================
# 7. /rolver ve /rolal KOMUTLARI
# ==========================================
@bot.tree.command(name="rolver", description="Rol verir.")
async def rolver(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"Rol verildi.", ephemeral=True)

@bot.tree.command(name="rolal", description="Rol alır.")
async def rolal(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return
    await member.remove_roles(role)
    await interaction.response.send_message(f"Rol alındı.", ephemeral=True)


# ==========================================
# 8. /rollerigeri KOMUTU
# ==========================================
@bot.tree.command(name="rollerigeri", description="Alınan rolleri iade eder.")
async def rollerigeri(interaction: discord.Interaction, member: discord.Member):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için Whitelist yetkiniz yok!", ephemeral=True)
        return

    if member.id in alinan_roller:
        roller = alinan_roller.pop(member.id)
        try:
            await member.add_roles(*roller, reason="Yetkili iadesi")
            await interaction.response.send_message("Roller iade edildi.", ephemeral=True)
        except Exception:
            await interaction.response.send_mes
