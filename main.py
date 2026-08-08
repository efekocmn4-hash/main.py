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
            await send_log(guild, discord.Embed(title="Kara Liste Ban Koruması", description=f"{user} manuel olarak banı açıldığı için tekrar banlandı!", color=discord.Color.red()))
        except: pass

@bot.tree.command(name="tamyasakla", description="Kullanıcıyı bu sunucudan veya tüm sunuculardan yasaklar (ID veya etiket ile).")
@app_commands.choices(secenek=[
    app_commands.Choice(name="Bu Sunucudan Yasakla", value="sunucu"),
    app_commands.Choice(name="Tüm Sunuculardan Yasakla", value="global")
])
async def tamyasakla(i: discord.Interaction, kullanici: str, secenek: app_commands.Choice[str], sebep: str):
    if i.user.id != i.guild.owner_id: return await i.response.send_message("Bu komutu sadece sunucu sahibi kullanabilir!", ephemeral=True)
    val = secenek.value
    
    clean_id = kullanici.strip("<@!>")
    target_user = None
    try:
        uid = int(clean_id)
        target_user = bot.get_user(uid) or await bot.fetch_user(uid)
    except:
        pass
        
    if not target_user:
        return await i.response.send_message("Geçerli bir kullanıcı bulunamadı (ID veya etiket hatalı).", ephemeral=True)

    hedef_sunucular = []
    if val == "sunucu":
        hedef_sunucular = [i.guild.name]
    elif val == "global":
        for guild in bot.guilds:
            if guild.get_member(target_user.id) is not None or guild.id == i.guild.id:
                hedef_sunucular.append(guild.name)

    try:
        sunucu_listesi_str_dm = "\n".join([f"-{s}" for s in hedef_sunucular]) if hedef_sunucular else f"-{i.guild.name}"
        dm_metin = f"{i.user.name} Tarafından Aşağıdaki sunuculardan yasaklandınız:\n{sunucu_listesi_str_dm}\n\nSebep:\n{sebep}"
        await target_user.send(dm_metin)
    except: pass

    etkilenen_sunucular = []
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

    sunucu_listesi_str = "\n".join([f"-{s}" for s in etkilenen_sunucular]) if etkilenen_sunucular else f"-{i.guild.name}"
    kanal_mesaj = f"{target_user.name} Kullanıcısı Aşağıdaki sunuculardan yasaklandı:\n{sunucu_listesi_str}"
    
    await i.response.send_message(kanal_mesaj)
    await send_log(i.guild, discord.Embed(title="Tamyasak Eklendi", color=discord.Color.dark_red()).add_field(name="Kullanıcı", value=target_user.mention).add_field(name="Sebep", value=sebep).add_field(name="Etkilenen Sunucu Sayısı", value=str(len(etkilenen_sunucular))))

@bot.tree.command(name="tamyasakkaldir", description="Yasağı bu sunucudan veya tüm sunuculardan kaldırır (ID veya etiket ile).")
@app_commands.choices(secenek=[
    app_commands.Choice(name="Bu Sunucudan Yasak Kaldır", value="sunucu"),
    app_commands.Choice(name="Tüm Sunuculardan Kaldır", value="global")
])
async def tamyasakkaldir(i: discord.Interaction, kullanici: str, secenek: app_commands.Choice[str], sebep: str):
    if i.user.id != i.guild.owner_id: return await i.response.send_message("Bu komutu sadece sunucu sahibi kullanabilir!", ephemeral=True)
    val = secenek.value
    
    clean_id = kullanici.strip("<@!>")
    try: uid = int(clean_id)
    except: return await i.response.send_message("Lütfen geçerli bir kullanıcı ID'si veya etiket girin!", ephemeral=True)

    if val == "sunucu":
        b = oku("banlilar.txt")
        b.discard(str(uid))
        yaz("banlilar.txt", b)
        try: 
            await i.guild.unban(discord.Object(id=uid), reason=sebep)
        except: pass
        await i.response.send_message(f"Kullanıcının (ID: `{uid}`) bu sunucudaki yasağı kaldırıldı. Sebep: {sebep}", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Sunucu Tamyasak Kaldırıldı", color=discord.Color.green()).add_field(name="User ID", value=str(uid)).add_field(name="Sebep", value=sebep))

    elif val == "global":
        gb = oku("global_banlilar.txt")
        gb.discard(str(uid))
        yaz("global_banlilar.txt", gb)
        b = oku("banlilar.txt")
        b.discard(str(uid))
        yaz("banlilar.txt", b)
        count = 0
        for guild in bot.guilds:
            try:
                await guild.unban(discord.Object(id=uid), reason=sebep)
                count += 1
            except: pass
        await i.response.send_message(f"Kullanıcının (ID: `{uid}`) global yasağı kaldırıldı ({count} sunucuda işlem denendi). Sebep: {sebep}", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Global Tamyasak Kaldırıldı", color=discord.Color.green()).add_field(name="User ID", value=str(uid)).add_field(name="Sebep", value=sebep))

@bot.tree.command(name="log-kanal-ayarla", description="Log kanalını ayarla.")
async def log_kanal_ayarla(i: discord.Interaction, kanal: discord.TextChannel):
    if i.user.id != i.guild.owner_id and not i.user.guild_permissions.administrator: return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    data = {}
    if os.path.exists("logkanali.txt"):
        with open("logkanali.txt", "r") as f:
            for l in f:
                if len(p := l.strip().split(":")) == 2: data[int(p[0])] = int(p[1])
    data[i.guild.id] = kanal.id
    with open("logkanali.txt", "w") as f:
        for gid, cid in data.items(): f.write(f"{gid}:{cid}\n")
    await i.response.send_message("Log kanalı güncellendi.", ephemeral=True)
    await send_log(i.guild, discord.Embed(title="Log Kanalı Ayarlandı", description=f"{kanal.mention}", color=discord.Color.green()))

whitelist_group = app_commands.Group(name="whitelist", description="Beyaz liste yönetim komutları")

@whitelist_group.command(name="ekle", description="Beyaz listeye kullanıcı ekler.")
async def whitelist_ekle(i: discord.Interaction, member: discord.Member):
    if i.user.id != i.guild.owner_id and not i.user.guild_permissions.administrator: return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    whitelist_ids.add(member.id)
    await i.response.send_message(f"{member.mention} beyaz listeye eklendi.", ephemeral=True)

@whitelist_group.command(name="cikar", description="Beyaz listeden kullanıcı çıkarır.")
async def whitelist_cikar(i: discord.Interaction, member: discord.Member):
    if i.user.id != i.guild.owner_id and not i.user.guild_permissions.administrator: return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    if member.id in whitelist_ids:
        whitelist_ids.remove(member.id)
        await i.response.send_message(f"{member.mention} beyaz listeden çıkarıldı.", ephemeral=True)
    else: await i.response.send_message("Bu kullanıcı zaten beyaz listede yok.", ephemeral=True)

@whitelist_group.command(name="liste", description="Beyaz listedeki kullanıcıları gösterir.")
async def whitelist_liste(i: discord.Interaction):
    if not whitelist_ids: return await i.response.send_message("Beyaz liste boş.", ephemeral=True)
    await i.response.send_message(embed=discord.Embed(title="Whitelist", description=", ".join([f"<@{uid}>" for uid in whitelist_ids]), color=discord.Color.blue()), ephemeral=True)

bot.tree.add_command(whitelist_group)

@bot.tree.command(name="duyuru", description="Duyuru gönder.")
async def duyuru(i: discord.Interaction, kanal: discord.TextChannel, secim: str, baslik: str, mesaj: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    ping = "@everyone" if secim.lower() == "@everyone" else ("@here" if secim.lower() == "@here" else (" ".join([r.mention for r in i.guild.roles if r != i.guild.default_role]) if secim.lower() in ["tümroller", "tumroller"] else (getattr(discord.utils.get(i.guild.roles, name=secim) or i.guild.get_role(int(secim) if secim.isdigit() else 0), 'mention', secim))))
    try:
        await kanal.send(content=ping, embed=discord.Embed(title=baslik, description=mesaj, color=discord.Color.gold()))
        await i.response.send_message("Gönderildi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Duyuru Gönderildi", color=discord.Color.blue()).add_field(name="Kanal", value=kanal.mention))
    except Exception as e: await i.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="sil", description="Mesaj sil.")
async def sil(i: discord.Interaction, adet: int):
    if not whitelist_kontrol(i) or adet < 1: return await i.response.send_message("Yetkiniz yok veya geçersiz sayı!", ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:
        s = await i.channel.purge(limit=adet)
        await i.followup.send(f"{len(s)} mesaj silindi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Mesaj Silindi", color=discord.Color.dark_orange()).add_field(name="Adet", value=str(len(s))))
    except Exception as e: await i.followup.send(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="uyar", description="Kullanıcıyı uyar.")
async def uyar(i: discord.Interaction, member: discord.Member, sebep: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    w = oku("warns.txt")
    w[member.id] = w.get(member.id, 0) + 1
    yaz("warns.txt", w)
    
    tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = f"{tarih} Tarihinde {i.guild.name} İsimli sunucuda {i.user.name} Tarafından uyarıldınız\nSebep:{sebep}"
    
    if w[member.id] >= 3:
        try:
            await member.timeout(timedelta(minutes=30), reason="3 uyari siniri")
            w[member.id] = 0; yaz("warns.txt", w)
            msg += "\n(3 uyarı sınırına ulaştığınız için 30 dakika süreyle susturuldunuz.)"
        except: pass
        
    try:
        await member.send(msg)
    except: pass

    await i.response.send_message(embed=discord.Embed(title="Uyari", description=f"Kullanıcı uyarıldı. Toplam uyarı: {w.get(member.id, 0)}", color=discord.Color.orange()), ephemeral=True)
    await send_log(i.guild, discord.Embed(title="Kullanıcı Uyarıldı", color=discord.Color.yellow()).add_field(name="Kullanıcı", value=member.mention).add_field(name="Sebep", value=sebep).add_field(name="Toplam Uyarı", value=str(w.get(member.id, 0))))

@bot.tree.command(name="mute", description="Sustur.")
async def mute(i: discord.Interaction, member: discord.Member, dakika: int, sebep: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    try:
        await member.timeout(timedelta(minutes=dakika), reason=sebep)
        
        tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
        dm_msg = f"{tarih} Tarihinde {i.guild.name} İsimli sunucuda {i.user.name} Tarafından susturuldunuz\nSebep:{sebep}"
        try:
            await member.send(dm_msg)
        except: pass

        await i.response.send_message("Susturuldu ve kullanıcıya DM gönderildi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Mute Atıldı", color=discord.Color.red()).add_field(name="Kullanıcı", value=member.mention).add_field(name="Süre", value=f"{dakika} dk").add_field(name="Sebep", value=sebep))
    except Exception as e: await i.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="dm", description="DM gönder (ID veya etiket ile).")
async def dm(i: discord.Interaction, kullanici: str, mesaj: str):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    
    clean_id = kullanici.strip("<@!>")
    target_user = None
    try:
        uid = int(clean_id)
        target_user = bot.get_user(uid) or await bot.fetch_user(uid)
    except:
        pass
        
    if not target_user:
        return await i.response.send_message("Geçerli bir kullanıcı bulunamadı (ID veya etiket hatalı).", ephemeral=True)

    try:
        embed = discord.Embed(title="Yetkili Mesajı", description=mesaj, color=discord.Color.orange())
        embed.add_field(name="Gönderen Yetkili", value=f"{i.user.name} (`{i.user.id}`)", inline=False)
        await target_user.send(embed=embed)
        await i.response.send_message("Gönderildi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="DM Gönderildi", color=discord.Color.blue()).add_field(name="Alıcı", value=target_user.mention).add_field(name="Gönderen", value=i.user.mention))
    except Exception as e: 
        await i.response.send_message(f"DM gönderilemedi (Kullanıcının DM'leri kapalı olabilir): {e}", ephemeral=True)

@bot.tree.command(name="rolal", description="Rol al.")
async def rolal(i: discord.Interaction, member: discord.Member, role: discord.Role):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    d = oku("roller.txt")
    d.setdefault(member.id, [])
    if role.id not in d[member.id]:
        d[member.id].append(role.id)
        yaz("roller.txt", d)
    try:
        await member.remove_roles(role)
        await i.response.send_message("Rol alındı ve kaydedildi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Rol Alındı", color=discord.Color.dark_purple()).add_field(name="Kullanıcı", value=member.mention).add_field(name="Rol", value=role.name))
    except Exception as e:
        await i.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="tümrolleri-geri-ver", description="Rolleri geri ver.")
async def tum_rolleri_geri_ver(i: discord.Interaction, member: discord.Member):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    d = oku("roller.txt")
    if member.id not in d or not d[member.id]: return await i.response.send_message("Kayıtlı rol yok.", ephemeral=True)
    roles = [i.guild.get_role(rid) for rid in d[member.id] if i.guild.get_role(rid)]
    if not roles: return await i.response.send_message("Geçerli rol bulunamadı.", ephemeral=True)
    try:
        await member.add_roles(*roles)
        d[member.id] = []
        yaz("roller.txt", d)
        await i.response.send_message("Roller geri verildi.", ephemeral=True)
        await send_log(i.guild, discord.Embed(title="Roller Geri Verildi", color=discord.Color.green()).add_field(name="Kullanıcı", value=member.mention))
    except Exception as e: await i.response.send_message(f"Hata: {e}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Destek Aç", style=discord.ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, i: discord.Interaction, button: discord.ui.Button):
        cat = discord.utils.get(i.guild.categories, name="DESTEK TALEPLERI") or await i.guild.create_category("DESTEK TALEPLERI")
        ch = await i.guild.create_text_channel(f"destek-{i.user.name}", category=cat, overwrites={i.guild.default_role: discord.PermissionOverwrite(read_messages=False), i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), i.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)})
        await ch.send(i.user.mention, embed=discord.Embed(title="Destek", description="Yetkililer ilgilenecek.", color=discord.Color.gold()), view=discord.ui.View().add_item(discord.ui.Button(label="Kapat", style=discord.ButtonStyle.red, custom_id="close_ticket")))
        await i.response.send_message(f"Açıldı: {ch.mention}", ephemeral=True)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "close_ticket":
        await interaction.response.send_message("Kanal kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-olustur", description="Panel kur.")
async def ticket_olustur(i: discord.Interaction):
    if not whitelist_kontrol(i): return await i.response.send_message("Yetkiniz yok.", ephemeral=True)
    await i.channel.send(embed=discord.Embed(title="Destek Sistemi", description="Talep açmak için tıklayın.", color=discord.Color.blurple()), view=TicketView())
    await i.response.send_message("Panel kuruldu.", ephemeral=True)

bot.run(TOKEN)
    
