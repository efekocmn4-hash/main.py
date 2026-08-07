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

whitelist_ids = set()

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

@bot.tree.command(name="duyuru", description="Duyuru atar.")
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
    except Exception:
        await interaction.response.send_message("Kullanıcının DM kutusu kapalı.", ephemeral=True)

@bot.tree.command(name="rolal", description="Kullanıcıdan rol alır ve kaydeder.")
async def rolal(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    data = get_roles()
    if member.id not in data: data[member.id] = []
    if role.id not in data[member.id]:
        data[member.id].append(role.id)
        save_roles(data)
    try:
        await member.remove_roles(role)
        await interaction.response.send_message(f"**{role.name}** alındı ve kaydedildi.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="tümrolleri-geri-ver", description="Alınan rolleri geri yükler.")
async def tum_rolleri_geri_ver(interaction: discord.Interaction, member: discord.Member):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    data = get_roles()
    if member.id not in data or not data[member.id]:
        await interaction.response.send_message("Kayıtlı rol bulunamadı.", ephemeral=True)
        return
    roles_to_add = [interaction.guild.get_role(rid) for rid in data[member.id] if interaction.guild.get_role(rid)]
    if not roles_to_add:
        await interaction.response.send_message("Geçerli rol bulunamadı.", ephemeral=True)
        return
    try:
        await member.add_roles(*roles_to_add)
        rol_isimleri = ", ".join([r.name for r in roles_to_add])
        data[member.id] = []
        save_roles(data)
        await interaction.response.send_message(f"Geri verilen roller: **{rol_isimleri}**", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)

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
        embed = discord.Embed(title="Destek Talebi", description="Yetkililer ilgilenecektir.", color=discord.Color.gold())
        await channel.send(f"@here {interaction.user.mention}", embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"Kanalınız açıldı: {channel.mention}", ephemeral=True)

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Sahiplen 🙋‍♂️", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"Talep sahiplenildi: {interaction.user.mention}")

    @discord.ui.button(label="Talebi Kapat 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Kanal 3 saniye içinde kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-olustur", description="Destek paneli kurar.")
async def ticket_olustur(interaction: discord.Interaction):
    if not whitelist_kontrol(interaction):
        await interaction.response.send_message("Yetkiniz yok!", ephemeral=True)
        return
    embed = discord.Embed(title="🎫 Destek Sistemi", description="Talep açmak için tıklayın.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Panel kuruldu.", ephemeral=True)

if __name__ == "__main__":
    keep_alive() # Web sunucusunu başlatır, Railway'in botu uyutmasını engeller
    bot.run(TOKEN)
                
