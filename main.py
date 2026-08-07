import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta
from flask import Flask
from threading import Thread

# --- Railway İçin Web Sunucusu ---
app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

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
            f.write(str(uid) + "\n")

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
            f.write(str(uid) + ":" + str(count) + "\n")

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
            f.write(str(uid) + ":" + ",".join(map(str, rids)) + "\n")

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
            f.write(str(gid) + ":" + str(cid) + "\n")

def get_command_perms():
    data = {}
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
                f.write(str(gid) + ":" + cmd + ":" + ",".join(map(str, rids)) + "\n")

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
    if interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator or interaction.user.id in whitelist_ids:
        return True
    
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
        print("Komutlar senkronize edildi.")
    except Exception as e:
        print("Senkronizasyon hatasi:", e)
    print("Bot Hazir:", bot.user)

@bot.event
async def on_member_unban(guild, user):
    banlilar = get_banlilar()
    if str(user.id) in banlilar:
        try:
            await guild.ban(user, reason="Kalici Guvenlik")
        except Exception:
            pass

@bot.event
async def on_member_update(before, after):
    if len(after.roles) > len(before.roles):
        new_role = next((role for role in after.roles if role not in before.roles), None)
        if new_role and new_role.permissions.administrator and not after.guild_owner:
            try:
                await after.edit(roles=[r for r in before.roles], reason="Izinsiz Yonetici Engellendi")
                embed = discord.Embed(
                    title="IZINSIZ YONETICI ENGELLENDI",
                    description="Kullaniciya izinsiz Yonetici yetkisi verildiği için yetki geri alindi.",
                    color=discord.Color.red()
                )
                await send_log(after.guild, embed)
            except Exception:
                pass

@bot.tree.command(name="komut-yetki-ekle", description="Bir komutu belirli bir role acar.")
async def komut_yetki_ekle(interaction: discord.Interaction, komut_adi: str, role: discord.Role):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid not in perms: perms[gid] = {}
    if komut_adi not in perms[gid]: perms[gid][komut_adi] = []
    
    if role.id not in perms[gid][komut_adi]:
        perms[gid][komut_adi].append(role.id)
        save_command_perms(perms)
        await interaction.response.send_message("Rol basariyla yetkilendirildi.", ephemeral=True)
    else:
        await interaction.response.send_message("Bu rol zaten yetkili.", ephemeral=True)

@bot.tree.command(name="komut-yetki-kaldir", description="Rol yetkisini kaldirir.")
async def komut_yetki_kaldir(interaction: discord.Interaction, komut_adi: str, role: discord.Role):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid in perms and komut_adi in perms[gid] and role.id in perms[gid][komut_adi]:
        perms[gid][komut_adi].remove(role.id)
        if not perms[gid][komut_adi]: del perms[gid][komut_adi]
        save_command_perms(perms)
        await interaction.response.send_message("Rol yetkisi kaldirildi.", ephemeral=True)
    else:
        await interaction.response.send_message("Yetki bulunamadi.", ephemeral=True)

@bot.tree.command(name="komut-yetki-liste", description="Yetkileri listeler.")
async def komut_yetki_liste(interaction: discord.Interaction):
    perms = get_command_perms()
    gid = interaction.guild.id
    if gid not in perms or not perms[gid]:
        await interaction.response.send_message("Yetkilendirilmis komut yok.", ephemeral=True)
        return
    
    embed = discord.Embed(title="Komut Yetki Listesi", color=discord.Color.blue())
    for cmd, rids in perms[gid].items():
        role_mentions = ", ".join(["<@&" + str(rid) + ">" for rid in rids])
        embed.add_field(name="/" + cmd, value=role_mentions, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="log-kanal-ayarla", description="Log kanalini ayarlar.")
async def log_kanal_ayarla(interaction: discord.Interaction, kanal: discord.TextChannel):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    save_log_channel(interaction.guild.id, kanal.id)
    await interaction.response.send_message("Log kanali güncellendi.", ephemeral=True)

@bot.tree.command(name="whitelist-ekle", description="Beyaz listeye ekler.")
async def whitelist_ekle(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    whitelist_ids.add(member.id)
    await interaction.response.send_message("Beyaz listeye eklendi.", ephemeral=True)

@bot.tree.command(name="whitelist-cikar", description="Beyaz listeden cikarir.")
async def whitelist_cikar(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    if member.id in whitelist_ids:
        whitelist_ids.remove(member.id)
        await interaction.response.send_message("Beyaz listeden cikarildi.", ephemeral=True)
    else:
        await interaction.response.send_message("Zaten listede yok.", ephemeral=True)

@bot.tree.command(name="whitelist-liste", description="Beyaz listeyi gösterir.")
async def whitelist_liste(interaction: discord.Interaction):
    if not whitelist_ids:
        await interaction.response.send_message("Liste bos.", ephemeral=True)
        return
    uyeler = ", ".join(["<@" + str(uid) + ">" for uid in whitelist_ids])
    embed = discord.Embed(title="Whitelist Listesi", description=uyeler, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="duyuru", description="Duyuru gonderir.")
async def duyuru(interaction: discord.Interaction, kanal: discord.TextChannel, secim: str, baslik: str, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return

    embed = discord.Embed(title=baslik, description=mesaj, color=discord.Color.gold())
    
    ping_metni = ""
    if secim.lower() == "@everyone":
        ping_metni = "@everyone"
    elif secim.lower() == "@here":
        ping_metni = "@here"
    elif secim.lower() in ["tümroller", "tumroller"]:
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
        await interaction.response.send_message("Duyuru gonderildi.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("Hata olustu: " + str(e), ephemeral=True)

@bot.tree.command(name="sil", description="Mesaj siler.")
async def sil(interaction: discord.Interaction, adet: int):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    if adet < 1:
        await interaction.response.send_message("1'den büyük sayi girin.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        silinenler = await interaction.channel.purge(limit=adet)
        await interaction.followup.send(str(len(silinenler)) + " mesaj silindi.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("Hata: " + str(e), ephemeral=True)

@bot.tree.command(name="uyar", description="Kullaniciyi uyarir.")
async def uyar(interaction: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return

    warns = get_warns()
    user_id = member.id
    warns[user_id] = warns.get(user_id, 0) + 1
    current_warns = warns[user_id]
    save_warns(warns)

    ceza_mesaji = "Uyarildiniz. Toplam uyari: " + str(current_warns)
    if current_warns >= 3:
        try:
            await member.timeout(timedelta(minutes=30), reason="3 uyari siniri")
            warns[user_id] = 0
            save_warns(warns)
            ceza_mesaji += " ve 30 dakika mute yediniz."
        except Exception:
            pass

    embed = discord.Embed(title="Uyari", description=ceza_mesaji, color=discord.Color.orange())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="mute", description="Kullaniciyi susturur.")
async def mute(interaction: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return

    try:
        await member.timeout(timedelta(minutes=dakika), reason=sebep)
        await interaction.response.send_message("Kullanici susturuldu.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("Hata: " + str(e), ephemeral=True)

@bot.tree.command(name="dm", description="DM gonderir.")
async def dm(interaction: discord.Interaction, member: discord.Member, mesaj: str):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    try:
        embed = discord.Embed(title="Yetkili Mesaji", description=mesaj, color=discord.Color.orange())
        await member.send(embed=embed)
        await interaction.response.send_message("DM gonderildi.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("DM kutusu kapali.", ephemeral=True)

@bot.tree.command(name="rolal", description="Rol alir.")
async def rolal(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    data = get_roles()
    if member.id not in data: data[member.id] = []
    if role.id not in data[member.id]:
        data[member.id].append(role.id)
        save_roles(data)
    try:
        await member.remove_roles(role)
        await interaction.response.send_message("Rol alindi ve kaydedildi.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("Hata: " + str(e), ephemeral=True)

@bot.tree.command(name="tümrolleri-geri-ver", description="Rolleri geri verir.")
async def tum_rolleri_geri_ver(interaction: discord.Interaction, member: discord.Member):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    data = get_roles()
    if member.id not in data or not data[member.id]:
        await interaction.response.send_message("Kayitli rol yok.", ephemeral=True)
        return
    roles_to_add = [interaction.guild.get_role(rid) for rid in data[member.id] if interaction.guild.get_role(rid)]
    if not roles_to_add:
        await interaction.response.send_message("Gecerli rol bulunamadi.", ephemeral=True)
        return
    try:
        await member.add_roles(*roles_to_add)
        data[member.id] = []
        save_roles(data)
        await interaction.response.send_message("Roller geri verildi.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("Hata: " + str(e), ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Destek Aç", style=discord.ButtonStyle.green, custom_id="create_ticket")
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
        channel = await guild.create_text_channel("destek-" + interaction.user.name, category=category, overwrites=overwrites)
        embed = discord.Embed(title="Destek", description="Yetkililer ilgilenecek.", color=discord.Color.gold())
        await channel.send(interaction.user.mention, embed=embed, view=TicketActionView())
        await interaction.response.send_message("Kanal acildi: " + channel.mention, ephemeral=True)

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kapat", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Kanal kapatiliyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-olustur", description="Panel kurar.")
async def ticket_olustur(interaction: discord.Interaction):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok.", ephemeral=True)
        return
    embed = discord.Embed(title="Destek Sistemi", description="Talep açmak için tiklayin.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Panel kuruldu.", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
        
