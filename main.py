import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# Render panelindeki anahtar adın 'DISCORD_TOKEN' olduğu için buraya göre ayarlandı
TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Botun güvenlik amaçlı çektiği rolleri saklamak için geçici sözlük
alinan_roller = {}

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} adet slash (/) komutu senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print(f"Bot Başarıyla Giriş Yaptı: {bot.user}")


# ==========================================
# GÜVENLİK SİSTEMİ: Yönetici Yetkisi Koruması
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
# 1. /tamyasak KOMUTU
# ==========================================
@bot.tree.command(name="tamyasak", description="Belirtilen kullanıcıyı botun bulunduğu tüm sunuculardan yasaklar.")
@app_commands.checks.has_permissions(ban_members=True)
async def tamyasak(interaction: discord.Interaction, member: discord.Member, sebep: str):
    await interaction.response.defer(thinking=True)
    await bildirim_gonder(member, "Tüm sunuculardan yasaklandınız.", sebep)
    
    basarili_sunucular = []
    for guild in bot.guilds:
        try:
            await guild.ban(member, reason=f"Tam Yasak - Yetkili: {interaction.user} | Sebep: {sebep}")
            basarili_sunucular.append(guild.name)
        except Exception:
            continue

    embed = discord.Embed(title="🚨 Tam Yasak Uygulandı", color=discord.Color.dark_red())
    embed.add_field(name="Hedef Kullanıcı", value=f"{member} (`{member.id}`)", inline=False)
    embed.add_field(name="İşlemi Yapan", value=interaction.user.mention, inline=False)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.add_field(name="Yasaklanan Sunucular", value=", ".join(basarili_sunucular) if basarili_sunucular else "Hiçbir sunucu", inline=False)
    
    await interaction.followup.send(embed=embed)


# ==========================================
# 2. /tamyasakkaldir KOMUTU
# ==========================================
class UnbanSelect(discord.ui.Select):
    def __init__(self, target_user):
        self.target_user = target_user
        options = [
            discord.SelectOption(label="Bu Sunucudan Kaldır", value="tek", description="Sadece komutun kullanıldığı sunucudaki yasağı kaldırır."),
            discord.SelectOption(label="Tüm Sunuculardan Kaldır", value="tum_kara", description="Botun bulunduğu tüm ortak sunuculardaki yasakları kaldırır.")
        ]
        super().__init__(placeholder="Yasağın kaldırılacağı kapsamı seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        secim = self.values[0]
        basarili_sunucular = []

        if secim == "tek":
            try:
                await interaction.guild.unban(self.target_user, reason=f"Yetkili: {interaction.user}")
                basarili_sunucular.append(interaction.guild.name)
            except Exception:
                await interaction.followup.send("Bu sunucuda yasak kaldırılamadı veya kullanıcı banlı değil.", ephemeral=True)
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
        embed.add_field(name="Kapsam", value="Tek Sunucu" if secim == "tek" else "Tüm Sunucular", inline=False)
        embed.add_field(name="İşlem Yapılan Sunucular", value=", ".join(basarili_sunucular), inline=False)
        
        await interaction.followup.send(embed=embed)

class UnbanView(discord.ui.View):
    def __init__(self, target_user):
        super().__init__(timeout=60)
        self.add_item(UnbanSelect(target_user))

@bot.tree.command(name="tamyasakkaldir", description="Bir kullanıcının yasağını seçmeli olarak kaldırır.")
@app_commands.checks.has_permissions(ban_members=True)
async def tamyasakkaldir(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
    except Exception:
        await interaction.response.send_message("Geçerli bir kullanıcı ID'si giriniz.", ephemeral=True)
        return

    view = UnbanView(user)
    embed = discord.Embed(title="🔓 Yasak Kaldırma Yönetimi", description=f"**{user}** için kapsam seçiniz.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================
# 3. /ticket-olustur KOMUTU
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
        
        embed = discord.Embed(title="Destek Talebi Oluşturuldu", description="Yetkililer kısa süre içinde sizinle ilgilenecektir.", color=discord.Color.gold())
        view = TicketCloseView()
        
        await channel.send(f"@here {interaction.user.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"Destek kanalınız oluşturuldu: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Kapat 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Destek talebi kapatılıyor, kanal 3 saniye içinde silinecektir...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-olustur", description="Sunucuda destek paneli kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_olustur(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 Destek Sistemi", description="Destek talebi açmak için aşağıdaki butona tıklayın.", color=discord.Color.blurple())
    view = TicketCreateView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Destek paneli başarıyla kuruldu.", ephemeral=True)


# ==========================================
# 4. /dm KOMUTU
# ==========================================
@bot.tree.command(name="dm", description="Bir kullanıcıya özel mesaj gönderir.")
@app_commands.checks.has_permissions(manage_messages=True)
async def dm(interaction: discord.Interaction, member: discord.Member, mesaj: str):
    try:
        embed = discord.Embed(title="📬 Yetkili Mesajı", description=mesaj, color=discord.Color.orange())
        embed.set_footer(text=f"Sunucu: {interaction.guild.name}")
        await member.send(embed=embed)
        await interaction.response.send_message(f"Başarıyla {member.mention} adlı kullanıcıya DM gönderildi.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Kullanıcının DM kutusu kapalı olabilir.", ephemeral=True)


# ==========================================
# 5. /rolver ve /rolal KOMUTLARI
# ==========================================
@bot.tree.command(name="rolver", description="Kullanıcıya belirtilen rolü verir.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rolver(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"{member.mention} adlı üyeye **{role.name}** rolü verildi.", ephemeral=True)

@bot.tree.command(name="rolal", description="Kullanıcıdan belirtilen rolü alır.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rolal(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"{member.mention} adlı üyeden **{role.name}** rolü alındı.", ephemeral=True)


# ==========================================
# 6. /rollerigeri KOMUTU (Çekilen Rolleri İade)
# ==========================================
@bot.tree.command(name="rollerigeri", description="Güvenlik sistemi tarafından alınan rolleri anında geri verir.")
@app_commands.checks.has_permissions(administrator=True)
async def rollerigeri(interaction: discord.Interaction, member: discord.Member):
    if member.id in alinan_roller:
        roller = alinan_roller.pop(member.id)
        try:
            await member.add_roles(*roller, reason=f"Yetkili iadesi - İşlemi Yapan: {interaction.user}")
            await interaction.response.send_message(f"Başarıyla **{member}** adlı yetkilinin eski rolleri geri verildi.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Roller iade edilirken bir hata oluştu (Yetkim yetersiz olabilir).", ephemeral=True)
    else:
        await interaction.response.send_message("Bu kullanıcının sistemde kayıtlı alınmış bir rolü bulunmuyor.", ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
                       
