import os, discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta, datetime
import asyncio
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Bot aktif!"
Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

TOKEN = os.environ.get("DISCORD_TOKEN")
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
whitelist_ids = set()

def oku(dosya):
    if not os.path.exists(dosya): return {} if "roller" in dosya or "komut" in dosya else set()
    with open(dosya, "r") as f:
        if "roller" in dosya:
            d = {}
            for l in f:
                p = l.strip().split(":")
                if len(p) == 2: d[int(p[0])] = [int(r) for r in p[1].split(",") if r]
            return d
        if "komut" in dosya:
            d = {}
            for l in f:
                p = l.strip().split(":")
                if len(p) == 3: d.setdefault(int(p[0]), {})[p[1]] = [int(r) for r in p[2].split(",") if r]
            return d
        if "warns" in dosya:
            d = {}
            for l in f:
                p = l.strip().split(":")
                if len(p) == 2: d[int(p[0])] = int(p[1])
            return d
        return set(l.strip() for l in f if l.strip())

def yaz(dosya, veri):
    with open(dosya, "w") as f:
        if isinstance(veri, dict):
            for k, v in veri.items():
                if isinstance(v, dict):
                    for sk, sv in v.items(): f.write(f"{k}:{sk}:{','.join(map(str, sv))}\n")
                else: f.write(f"{k}:{v}\n" if not isinstance(v, list) else f"{k}:{','.join(map(str, v))}\n")
        else:
            for item in veri: f.write(f"{item}\n")

def log_kanal_getir(gid):
    if not os.path.exists("logkanali.txt"): return None
    with open("logkanali.txt", "r") as f:
        for l in f:
            p = l.strip().split(":")
            if len(p) == 2 and int(p[0]) == gid: return int(p[1])
    return None

async def send_log(guild, embed):
    cid = log_kanal_getir(guild.id)
    if cid and (ch := guild.get_channel(cid)):
        try: await ch.send(embed=embed)
        except: pass

def whitelist_kontrol(i: discord.Interaction):
    if i.user.id == i.guild.owner_id or i.user.guild_permissions.administrator or i.user.id in whitelist_ids: return True
    perms = oku("komutyetkileri.txt")
    if i.guild.id in perms and i.command.name in perms[i.guild.id]:
        if any(r.id in perms[i.guild.id][i.command.name] for r in i.user.roles): return True
    return False

@bot.event
async def on_ready():
    try: await bot.tree.sync()
    except: pass
    print("Bot Hazir:", bot.user)

@bot.event
async def on_member_join(member):
    if str(member.id) in oku("global_banlilar.txt"):
        try: await member.ban(reason="Global Kara Liste Koruması!")
        except: pass

@bot.event
async def on_member_unban(guild, user):
    if str(user.id) in oku("banlilar.txt") or str(user.id) in oku("global_banlilar.txt"):
        try:
            await guild.ban(user, reason="Kara liste koruması!")
            await send_log(guild, discord.Embed(title="🛡️ Kara Liste Ban Koruması", description=f"{user.mention} (`@{user.name}`) manuel olarak banı açıldığı için tekrar banlandı!", color=discord.Color.red()))
        except: pass

@bot.tree.command(name="tamyasakla", description="Kullanıcıyı yasaklar.")
@app_commands.choices(secenek=[app_commands.Choice(name="Bu Sunucudan Yasakla", value="sunucu"), app_commands.Choice(name="Tüm Sunuculardan Yasakla", value="global")])
async def tamyasakla(i: discord.Interaction, kullanici: str, secenek: app_commands.Choice[str], sebep: str):
    if i.user.id != i.guild.owner_id: return await i.response.send_message("Sadece sunucu sahibi kullanabilir!", ephemeral=True)
    
    clean_id = kullanici.strip("<@!>")
    try:
        uid = int(clean_id)
        target_user = bot.get_user(uid) or await bot.fetch_user(uid)
    except: return await i.response.send_message("Geçersiz kullanıcı.", ephemeral=True)

    etkilenen_sunucular = []
    val = secenek.value
    if val == "sunucu":
        b = oku("banlilar.txt")
        b.add(str(target_user.id))
        yaz("banlilar.txt", b)
        try: 
            await i.guild.ban(target_user, reason=sebep)
            etkilenen_sunucular.append(i.guild.name)
        except: pass
    elif val == "global":
        gb = oku("global_banlilar.txt")
        gb.add(str(target_user.id))
        yaz("global_banlilar.txt", gb)
        for guild in bot.guilds:
            try:
                await guild.ban(target_user, reason=sebep)
                etkilenen_sunucular.append(guild.name)
            except: pass

    islem_turu_metin = "bu sunucudan" if val == "sunucu" else "tüm sunuculardan"
    embed = discord.Embed(title="🛡️ Yasaklama İşlemi", description=f"{i.user.mention} (`@{i.user.name}`) tarafından {target_user.mention} (`@{target_user.name}`) kullanıcısı **{sebep}** sebebiyle {islem_turu_metin} yasaklandı.", color=discord.Color.dark_red())
    
    await i.response.send_message(embed=embed)
    await send_log(i.guild, embed)
    try: await target_user.send(embed=embed)
    except: pass

@bot.tree.command(name="tamyasakkaldir", description="Yasağı kaldırır.")
@app_commands.choices(secenek=[app_commands.Choice(name="Bu Sunucudan Yasak Kaldır", value="sunucu"), app_commands.Choice(name="Tüm Sunuculardan Kaldır", value="global")])
async def tamyasakkaldir(i: discord.Interaction, kullanici: str, secenek: app_commands.Choice[str], sebep: str):
    if i.user.id != i.guild.owner_id: return await i.response.send_message("Sadece sunucu sahibi kullanabilir!", ephemeral=True)
    
    clean_id = kullanici.strip("<@!>")
    try: uid = int(clean_id)
    except: return await i.response.send_message("Geçersiz ID.", ephemeral=True)

    if secenek.value == "sunucu":
        b = oku("banlilar.txt"); b.discard(str(uid)); yaz("banlilar.txt", b)
        try: await i.guild.unban(discord.Object(id=uid), reason=sebep)
        except: pass
    else:
        gb = oku("global_banlilar.txt"); gb.discard(str(uid)); yaz("global_banlilar.txt", gb)
        b = oku("banlilar.txt"); b.discard(str(uid)); yaz("banlilar.txt", b)
        for guild in bot.guilds:
            try: await guild.unban(discord.Object(id=uid), reason=sebep)
            except: pass

    embed = discord.Embed(title="🛡️ Yasak Kaldırma İşlemi", description=f"{i.user.mention} tarafından `<@{uid}>` kullanıcısının yasağı **{sebep}** sebebiyle kaldırıldı.", color=discord.Color.green())
    await i.response.send_message(embed=embed, ephemeral=True)
    await send_log(i.guild, embed)

@bot.tree.command(name="uyar", description="Kullanıcıyı uyar.")
async def uyar(i: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    w = oku("warns.txt")
    w[member.id] = w.get(member.id, 0) + 1
    yaz("warns.txt", w)
    
    embed = discord.Embed(title="⚠️ Uyarı İşlemi", description=f"{i.user.mention} (`@{i.user.name}`) tarafından {member.mention} (`@{member.name}`) kullanıcısı **{sebep}** sebebiyle uyarıldı. (Toplam Uyarı: {w.get(member.id, 0)})", color=discord.Color.orange())
    
    if w[member.id] >= 3:
        try:
            await member.timeout(timedelta(minutes=30), reason="3 uyari siniri")
            w[member.id] = 0; yaz("warns.txt", w)
            embed.description += "\n(3 uyarı sınırına ulaşıldığı için 30 dakika susturuldu.)"
        except: pass
        
    await i.response.send_message(embed=embed, ephemeral=True)
    await send_log(i.guild, embed)
    try: await member.send(embed=embed)
    except: pass

@bot.tree.command(name="mute", description="Sustur.")
async def mute(i: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    try:
        await member.timeout(timedelta(minutes=dakika), reason=sebep)
        embed = discord.Embed(title="🔇 Susturma İşlemi", description=f"{i.user.mention} (`@{i.user.name}`) tarafından {member.mention} (`@{member.name}`) kullanıcısı **{sebep}** sebebiyle {dakika} dakika susturuldu.", color=discord.Color.red())
        await i.response.send_message(embed=embed, ephemeral=True)
        await send_log(i.guild, embed)
        try: await member.send(embed=embed)
        except: pass
    except Exception as e: await i.response.send_message(f"Hata: {e}", ephemeral=True)

# ... Diğer komutlar (log-kanal-ayarla, whitelist, duyuru, sil, dm, rolal, ticket-olustur) aynen kalabilir ...

bot.run(TOKEN)
                                                
