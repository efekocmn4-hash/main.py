import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta
from flask import Flask
from threading import Thread

# --- Railway İçin Web Sunucusu (Botun Kapanmasını Önler) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ---------------------------------------------------------

TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BAN_FILE = "banlilar.txt"
WARN_FILE = "warns.txt"
ROLE_FILE = "roller.txt"
LOG_FILE = "logkanali.txt"
COMMAND_PERM_FILE = "komutyetkileri.txt"

def get_banlilar():
    if not os.path.exists(BAN_FILE): return set()
    with open(BAN_FILE, "r") as f:
        return set(line.strip() for line in f.readlines() if line.strip())

def save_banlilar(banlilar):
    with open(BAN_FILE, "w") as f:
        for uid in banlilar:
            f.write(f"{uid}\n")

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

def get_roles():
    data = {}
    if not os.path.exists(ROLE_FILE): return data
    with open(ROLE_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 2:
                uid = int(parts[0])
                rids = [int(r) for r in parts[1].split(",") if r]
                data[uid] = rids
    return data

def save_roles(data):
    with open(ROLE_FILE, "w") as f:
        for uid, rids in data.items():
            f.write(f"{uid}:" + ",".join(map(str, rids)) + "\n")

def get_log_channel(guild_id):
    if not os.path.exists(LOG_FILE): return None
    with open(LOG_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 2 and int(parts[0]) == guild_id:
                return int(parts[1])
    return None

def save_log_channel(guild_id, channel_id):
    data = {}
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    data[int(parts[0])] = int(parts[1])
    data[guild_id] = channel_id
    with open(LOG_FILE, "w") as f:
        for gid, cid in data.items():
            f.write(f"{gid}:{cid}\n")

# Komut yetki sistemi dosya fonksiyonları
def get_command_perms():
    data = {} # {guild_id: {komut_adi: [role_id1, role_id2]}}
    if not os.path.exists(COMMAND_PERM_FILE): return data
    with open(COMMAND_PERM_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 3:
                gid = int(parts[0])
                cmd = parts[1]
                rids = [int(r) for r in parts[2].split(",") if r]
                if gid not in data: data[gid] = {}
                data[gid][cmd] = rids
    return data

def save_command_perms(data):
    with open(COMMAND_PERM_FILE, "w") as f:
        for gid, cmds in data.items():
            for cmd, rids in cmds.items():
                f.write(f"{gid}:{cmd}:" + ",".join(map(str, rids)) + "\n")

async def send_log(guild, embed):
    cid = get_log_channel(guild.id)
    if cid:
        channel = guild.get_channel(cid)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

whitelist_ids = set()

def whitelist_kontrol(interaction: discord.Interaction) -> bool:
    # Sunucu sahibi, yönetici veya whitelist'te olanlar temel yetkilidir
    if interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator or interaction.user.id in whitelist_ids:
        return True
    
    # Ekstra rol bazlı komut yetkisi kontrolü
    perms = get_command_perms()
    guild_perms = perms.get(interaction.guild.id, {})
    cmd_name = interaction.command.name
    
    if cmd_name in guild_perms:
        allowed_role_ids = guild_perms[cmd_name]
        user_role_ids = [r.id for r in interaction.user.roles]
        if any(rid in user_role_ids for rid in allowed_role_ids):
            return True

    return False

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} komut senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print(f"Bot Hazır: {bot.user}")

@bot.event
async def on_member_unban(guild, user):
    banlilar = get_banlilar()
    if str(user.id) in banlilar:
        try:
            await guild.ban(user, reason="Kalıcı Güvenlik: Bot banı manuel kaldırılamaz!")
        except Exception:
            pass

@bot.event
async def on_member_update(before, after):
    if len(after.roles) > len(before.roles):
        new_role = next((role for role in after.roles if role not in before.roles), None)
        if new_role and new_role.permissions.administrator and not after.guild_owner:
            try:
                await after.edit(roles=[r for r in before.roles], reason="GÜVENLİK: İzinsiz Yönetici yetkisi engellendi!")
                embed = discord.Embed(
                    title="🚨 İZİNSİZ YÖNETİCİ ENGELLENDİ",
                    description=f"**{after}** adlı kullanıcıya izinsiz Yönetici yetkisi verildiği için yetki geri alındı.",
                    color=discord.Color.red()
                )
                await send_log(after.guild, embed)
            except Exception:
                pass

# --- KOMUT YETKİLENDİRME YÖNETİMİ ---
@bot.tree.command(name="komut-yetki-ekle", description="Bir komutu belirli bir role özel olarak açar.")
async def komut_yetki_ekle(interaction: discord.Interaction, komut_adi: str, role: discord.Role):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return
    
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid not in perms: perms[gid] = {}
    if komut_adi not in perms[gid]: perms[gid][komut_adi] = []
    
    if role.id not in perms[gid][komut_adi]:
        perms[gid][komut_adi].append(role.id)
        save_command_perms(perms)
        await interaction.response.send_message(f"Başarılı! Artık **{role.name}** rolündekiler `/{komut_adi}` komutunu kullanabilecek.", ephemeral=True)
    else:
        await interaction.response.send_message("Bu rol zaten bu komut için yetkilendirilmiş.", ephemeral=True)

@bot.tree.command(name="komut-yetki-kaldir", description="Bir komut için rol yetkisini kaldırır.")
async def komut_yetki_kaldir(interaction: discord.Interaction, komut_adi: str, role: discord.Role):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return
    
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid in perms and komut_adi in perms[gid] and role.id in perms[gid][komut_adi]:
        perms[gid][komut_adi].remove(role.id)
        if not perms[gid][komut_adi]: del perms[gid][komut_adi]
        save_command_perms(perms)
        await interaction.response.send_message(f"**{role.name}** rolünün `/{komut_adi}` üzerindeki yetkisi kaldırıldı.", ephemeral=True)
    else:
        await interaction.response.send_message("Bu rol için böyle bir komut yetkisi bulunamadı.", ephemeral=True)

@bot.tree.command(name="komut-yetki-liste", description="Komutlara özel verilmiş rol yetkilerini listeler.")
async def komut_yetki_liste(interaction: discord.Interaction):
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid not in perms or not perms[gid]:
        await interaction.response.send_message("Bu sunucuda özel olarak yetkilendirilmiş bir komut bulunmuyor.", ephemeral=True)
        return
    
    embed = discord.Embed(title="🛡️ Komut Yetki Listesi", color=discord.Color.blue())
    for cmd, rids in perms[gid].items():
        role_mentions = ", ".join([f"<@&{rid}>" for rid in rids])
        embed.add_field(name=f"/{cmd}", value=role_mentions, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="log-kanal-ayarla", description="Log bildirimlerinin gönderileceği kanalı ayarlar.")
async def log_kanal_ayarla(interaction: discord.Interaction, kanal: discord.TextChannel):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Bu komutu sadece sunucu sahibi veya yöneticiler kullanabilir.", ephemeral=True)
        return
    save_log_channel(interaction.guild.id, kanal.id)
    embed = discord.Embed(title="⚙️ Log Kanalı Güncellendi", description=f"Loglar başarıyla {kanal.mention} kanalına yönlendirildi.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

@bot.tree.command(name="duyuru", description="Duyuru atar (Seçime 'tümroller' yazarak tüm rolleri etiketleyebilirsin).")
async def duyuru(interaction: discord.Interaction, kanal: discord.TextChannel, secim: str, baslik: str, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için yetkiniz yok!", ephemeral=True)
        return

    embed = discord.Embed(title=f"📢 {baslik}", description=mesaj, color=discord.Color.gold())
    embed.set_footer(text=f"Yetkili: {interaction.user}", icon_url=interaction.user.display_avatar.url)

    ping_metni = ""
    if secim.lower() == "@everyone":
        ping_metni = "@everyone"
    elif secim.lower() == "@here":
        ping_metni = "@here"
    elif secim.lower() == "tümroller" or secim.lower() == "tumroller":
        ping_metni = " ".join([r.mention for r in interaction.guild.roles if r != interaction.guild.default_role])
    else:
        role = discord.utils.get(interaction.guild.roles, name=secim)
        if not role:
            try:
                role = interaction.guild.get_role(int(secim))
            except ValueError:
                pass
        ping_metni = role.mention if role else secim

    try:
        await kanal.send(content=ping_metni, embed=embed)
        await interaction.response.send_message(f"Duyuru başarıyla {kanal.mention} kanalına gönderildi.", ephemeral=True)
        
        log_embed = discord.Embed(title="📢 Duyuru Gönderildi", color=discord.Color.blue())
        log_embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        log_embed.add_field(name="Kanal", value=kanal.mention, inline=False)
        await send_log(interaction.guild, log_embed)
    except Exception as e:
        await interaction.response.send_message(f"Duyuru gönderilirken hata oluştu: {e}", ephemeral=True)

@bot.tree.command(name="sil", description="Mesaj siler.")
async def sil(interaction: discord.Interaction, adet: int):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    if adet < 1:
        await interaction.response.send_message("1'den büyük sayı girin.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        silinenler = await interaction.channel.purge(limit=adet)
        await interaction.followup.send(f"**{len(silinenler)}** mesaj silindi.", ephemeral=True)
        
        log_embed = discord.Embed(title="🗑️ Mesaj Silindi", color=discord.Color.dark_orange())
        log_embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        log_embed.add_field(name="Kanal", value=interaction.channel.mention, inline=False)
        log_embed.add_field(name="Silinen Adet", value=str(len(silinenler)), inline=False)
        await send_log(interaction.guild, log_embed)
    except Exception as e:
        await interaction.followup.send(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="uyar", description="Kullanıcıyı uyarır (3. uyarıda mute).")
async def uyar(interaction: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return

    warns = get_warns()
    user_id = member.id
    warns[user_id] = warns.get(user_id, 0) + 1
    current_warns = warns[user_id]
    save_warns(warns)

    try:
        dm_embed = discord.Embed(title="⚠️ Uyarı Aldınız!", description=f"**{interaction.guild.name}** sunucusunda uyarıldınız.", color=discord.Color.yellow())
        dm_embed.add_field(name="Sebep", value=sebep, inline=False)
        dm_embed.add_field(name="Toplam Uyarı", value=str(current_warns), inline=False)
        await member.send(embed=dm_embed)
    except Exception:
        pass

    ceza_mesaji = f"{member.mention} uyarıldı. (Toplam: {current_warns})"
    if current_warns >= 3:
        try:
            await member.timeout(timedelta(minutes=30), reason="3 uyarı sınırı")
            warns[user_id] = 0
            save_warns(warns)
            ceza_mesaji += "\n🚨 3 uyarıyı aştığı için **30 dakika** mute yedi!"
        except Exception as e:
            ceza_mesaji += f"\n(Mute atılamadı: {e})"

    embed = discord.Embed(title="⚠️ Uyarı", description=ceza_mesaji, color=discord.Color.orange())
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    log_embed = discord.Embed(title="⚠️ Kullanıcı Uyarıldı", color=discord.Color.yellow())
    log_embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
    log_embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
    log_embed.add_field(name="Sebep", value=sebep, inline=False)
    log_embed.add_field(name="Toplam Uyarı", value=str(current_warns), inline=False)
    await send_log(interaction.guild, log_embed)

@bot.tree.command(name="mute", description="Kullanıcıya süre, sebep ve DM bildirimiyle zaman aşımı uygular.")
async def mute(interaction: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Bu komutu kullanmak için yetkiniz yok!", ephemeral=True)
        return

    durum_suresi = timedelta(minutes=dakika)
    try:
        await member.timeout(durum_suresi, reason=sebep)
        
        try:
            dm_embed = discord.Embed(title="🔇 Susturuldunuz (Mute)", color=discord.Color.red())
            dm_embed.add_field(name="Sunucu", value=interaction.guild.name, inline=False)
            dm_embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
            dm_embed.add_field(name="Sebep", value=sebep, inline=False)
            dm_embed.set_footer(text=f"İşlemi Yapan Yetkili: {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await member.send(embed=dm_embed)
        except Exception:
            pass

        embed = discord.Embed(title="🔇 Kullanıcı Susturuldu", color=discord.Color.orange())
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        log_embed = discord.Embed(title="🔇 Mute Atıldı", color=discord.Color.red())
        log_embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        log_embed.add_field(name="Süre", value=f"{dakika} dakika", inline=False)
        log_embed.add_field(name="Sebep", value=sebep, inline=False)
        log_embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        await send_log(interaction.guild, log_embed)
    except Exception as e:
        await interaction.response.send_message(f"Mute atılırken hata oluştu: {e}", ephemeral=True)

@bot.tree.command(name="dm", description="Kullanıcıya DM gönderir.")
async def dm(interaction: discord.Interaction, member: discord.Member, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    try:
        embed = discord.Embed(title="📬 Yetkili Mesajı", description=mesaj, color=discord.Color.orange())
        embed.set_footer(text=f"Gönderen: {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await member.send(embed=embed)
        await interaction.response.send_message(f"**{member}** kişisine DM gönderildi.", ephemeral=True)
        
        log_embed = discord.Embed(title="📬 Yetkili DM Gönderdi", color=discord.Color.blue())
        log_embed.add_field(name="Alıcı", value=member.mention, inline=False)
        log_embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        await send_log(interaction.guild, log_embed)
    except Exception:
        await interaction.response.send_message("Kullanıcının DM kutusu kapalı.", ephemeral=True)

@bot.tree.command(name="rolal", description="Kullanıcıdan rol alır ve kaydeder.")
async def rolal(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    data = get_roles()
    if me
