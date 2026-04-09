import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp
import asyncio
import logging
import random
import os
from collections import deque

MUSIC_CHANNEL_ID = int(os.getenv('MUSIC_CHANNEL_ID', 0))

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

YDL_OPTS_PLAYLIST = {
    'quiet': True,
    'extract_flat': 'in_playlist',
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
}

# ─── Repeat mode labels ───────────────────────────────────────────────────────
REPEAT_LABELS = {0: '➡️ Sem repetição', 1: '🔂 Repetindo esta música', 2: '🔁 Repetindo fila toda'}


# ─── Embed do painel ──────────────────────────────────────────────────────────

def build_embed(state: dict) -> discord.Embed:
    current = state.get('current')

    if not current:
        embed = discord.Embed(
            title='🎵 Music Player',
            description='**Digite o nome de uma música ou uma URL do YouTube aqui para tocar!**\n\nSuporta pesquisa por texto, links de vídeos e playlists.',
            color=discord.Color.blurple()
        )
        embed.set_footer(text='Nenhuma música tocando no momento.')
        return embed

    title, url = current
    paused = state.get('paused', False)
    repeat = state.get('repeat', 0)
    volume = state.get('volume', 0.5)
    queue_titles = state.get('queue_titles', [])

    status = '⏸️ Pausado' if paused else '▶️ Tocando agora'
    color = discord.Color.orange() if paused else discord.Color.green()

    embed = discord.Embed(
        title=status,
        description=f'**[{title}]({url})**',
        color=color
    )
    embed.add_field(name='🔁 Repeat', value=REPEAT_LABELS[repeat], inline=True)
    embed.add_field(name='🔊 Volume', value=f'{int(volume * 100)}%', inline=True)

    if queue_titles:
        preview = '\n'.join(f'`{i+1}.` {t}' for i, t in enumerate(queue_titles[:5]))
        if len(queue_titles) > 5:
            preview += f'\n_...e mais {len(queue_titles) - 5} música(s)_'
        embed.add_field(name=f'📋 Fila ({len(queue_titles)})', value=preview, inline=False)
    else:
        embed.add_field(name='📋 Fila', value='Vazia', inline=False)

    embed.set_footer(text='Use os botões abaixo para controlar o player.')
    return embed


# ─── Painel de botões ─────────────────────────────────────────────────────────

class MusicView(discord.ui.View):
    def __init__(self, cog: 'Music'):
        super().__init__(timeout=None)
        self.cog = cog

    async def _get_state(self, interaction: discord.Interaction) -> dict:
        return self.cog.get_state(interaction.guild_id)

    # ── Linha 1: Controles de reprodução ──────────────────────────────────────

    @discord.ui.button(emoji='⏮️', style=discord.ButtonStyle.secondary, custom_id='music:prev', row=0)
    async def btn_prev(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        history = state.get('history', deque())
        if history:
            prev = history.pop()
            # Coloca a atual de volta no início da fila
            if state['current']:
                state['queues'].insert(0, state['current'])
                state['queue_titles'].insert(0, state['current'][0])
            state['queues'].insert(0, prev)
            state['queue_titles'].insert(0, prev[0])
            vc = interaction.guild.voice_client
            if vc and (vc.is_playing() or vc.is_paused()):
                state['skip_to_next'] = True
                vc.stop()
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.primary, custom_id='music:pause', row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.pause()
                state['paused'] = True
                button.emoji = '▶️'
            elif vc.is_paused():
                vc.resume()
                state['paused'] = False
                button.emoji = '⏸️'
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.secondary, custom_id='music:skip', row=0)
    async def btn_skip(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            # Ignora o repeat de track para forçar o skip
            state['force_skip'] = True
            vc.stop()
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger, custom_id='music:stop', row=0)
    async def btn_stop(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        state['queues'] = []
        state['queue_titles'] = []
        state['original_queues'] = []
        state['current'] = None
        state['repeat'] = 0
        state['history'] = deque(maxlen=10)
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await vc.disconnect()
        await self.cog.update_panel(interaction.guild)

    # ── Linha 2: Extras ───────────────────────────────────────────────────────

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary, custom_id='music:shuffle', row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        combined = list(zip(state['queues'], state['queue_titles']))
        random.shuffle(combined)
        if combined:
            state['queues'], state['queue_titles'] = map(list, zip(*combined))
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.secondary, custom_id='music:repeat', row=1)
    async def btn_repeat(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        new_mode = (state.get('repeat', 0) + 1) % 3
        state['repeat'] = new_mode
        # Salva snapshot da fila para repeat de fila toda
        if new_mode == 2 and not state.get('original_queues'):
            state['original_queues'] = []
            if state['current']:
                state['original_queues'].append(state['current'])
            state['original_queues'].extend(state['queues'])
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='🔉', style=discord.ButtonStyle.secondary, custom_id='music:vol_down', row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = max(0.1, round(state['volume'] - 0.1, 1))
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state['volume']
        await self.cog.update_panel(interaction.guild)

    @discord.ui.button(emoji='🔊', style=discord.ButtonStyle.secondary, custom_id='music:vol_up', row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        state = self.cog.get_state(interaction.guild_id)
        state['volume'] = min(2.0, round(state['volume'] + 0.1, 1))
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state['volume']
        await self.cog.update_panel(interaction.guild)


# ─── Select de resultados de busca ────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    def __init__(self, results: list, cog: 'Music', guild: discord.Guild, voice_channel):
        self.cog = cog
        self.guild = guild
        self.voice_channel = voice_channel
        options = [
            discord.SelectOption(label=r['title'][:100], value=str(i))
            for i, r in enumerate(results[:5])
        ]
        super().__init__(placeholder='Selecione uma música...', options=options)
        self.results = results

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected = self.results[int(self.values[0])]
        state = self.cog.get_state(self.guild.id)
        # IMPORTANTE: ordem correta é (title, url) — igual ao resto do código
        state['queues'].append((selected['title'], selected['url']))
        state['queue_titles'].append(selected['title'])
        # Deleta a mensagem de seleção
        try:
            await interaction.message.delete()
        except Exception:
            pass
        if not self.guild.voice_client or (
            not self.guild.voice_client.is_playing() and
            not self.guild.voice_client.is_paused()
        ):
            await self.cog.play_next(self.guild)
        else:
            await self.cog.update_panel(self.guild)


class SearchView(discord.ui.View):
    def __init__(self, results, cog, guild, voice_channel):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(results, cog, guild, voice_channel))

    async def on_timeout(self):
        self.stop()


# ─── Cog principal ────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, dict] = {}
        self._panel_messages: dict[int, discord.Message] = {}

    def get_state(self, guild_id: int) -> dict:
        if guild_id not in self._states:
            self._states[guild_id] = {
                'queues': [],
                'queue_titles': [],
                'original_queues': [],
                'current': None,         # tupla (title, url)
                'paused': False,
                'repeat': 0,             # 0=off 1=track 2=queue
                'volume': 1.0,
                'history': deque(maxlen=10),
                'force_skip': False,
            }
        return self._states[guild_id]

    # ── Painel ────────────────────────────────────────────────────────────────

    async def get_or_create_panel(self, guild: discord.Guild) -> discord.Message:
        channel = guild.get_channel(MUSIC_CHANNEL_ID)
        if not channel:
            raise ValueError(f'Canal {MUSIC_CHANNEL_ID} não encontrado.')

        state = self.get_state(guild.id)
        view = MusicView(self)

        if guild.id in self._panel_messages:
            try:
                msg = self._panel_messages[guild.id]
                await msg.edit(embed=build_embed(state), view=view)
                return msg
            except discord.NotFound:
                pass

        # Limpa msgs antigas do bot para manter o canal organizado
        async for old_msg in channel.history(limit=30):
            if old_msg.author == self.bot.user:
                try:
                    await old_msg.delete()
                except Exception:
                    pass

        msg = await channel.send(embed=build_embed(state), view=view)
        self._panel_messages[guild.id] = msg
        return msg

    async def update_panel(self, guild: discord.Guild):
        state = self.get_state(guild.id)
        view = MusicView(self)
        try:
            msg = self._panel_messages.get(guild.id)
            if msg:
                await msg.edit(embed=build_embed(state), view=view)
            else:
                await self.get_or_create_panel(guild)
        except discord.NotFound:
            await self.get_or_create_panel(guild)
        except Exception as e:
            logging.error(f'Erro ao atualizar painel: {e}')

    # ── Reprodução ────────────────────────────────────────────────────────────

    async def play_next(self, guild: discord.Guild):
        state = self.get_state(guild.id)
        vc = guild.voice_client

        if not vc or not vc.is_connected():
            state['current'] = None
            await self.update_panel(guild)
            return

        force_skip = state.pop('force_skip', False)

        # Repeat track (ignora se foi skip forçado)
        if not force_skip and state['repeat'] == 1 and state['current']:
            title, url = state['current']
            await self._play_track(guild, url, title)
            return

        # Repeat queue
        if state['repeat'] == 2 and not state['queues']:
            if state['original_queues']:
                state['queues'] = list(state['original_queues'])
                state['queue_titles'] = [s[0] for s in state['original_queues']]

        if not state['queues']:
            state['current'] = None
            await self.update_panel(guild)
            channel = guild.get_channel(MUSIC_CHANNEL_ID)
            if channel:
                await channel.send('✅ A fila terminou!', delete_after=10)
            if vc.is_connected():
                await vc.disconnect()
            return

        title, url = state['queues'].pop(0)
        state['queue_titles'].pop(0)

        if state['current']:
            state['history'].append(state['current'])

        state['current'] = (title, url)
        state['paused'] = False

        if state['repeat'] == 2 and not state.get('original_queues'):
            state['original_queues'] = [state['current']] + list(state['queues'])

        await self._play_track(guild, url, title)

    async def _play_track(self, guild: discord.Guild, url: str, title: str):
        state = self.get_state(guild.id)
        vc = guild.voice_client
        if not vc:
            return

        loop = asyncio.get_event_loop()
        try:
            # Opções específicas para extração de stream (sem extract_flat)
            ydl_stream_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'noplaylist': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'no_warnings': True,
                'source_address': '0.0.0.0',
                'extract_flat': False,          # garante extração completa
            }
            with yt_dlp.YoutubeDL(ydl_stream_opts) as ydl:
                info = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )

            # Log das chaves disponíveis para debug
            logging.debug(f"yt-dlp info keys para '{title}': {list(info.keys())}")

            stream_url = None

            # 1) URL direta no topo (formato já selecionado)
            if info.get('url'):
                stream_url = info['url']

            # 2) requested_formats (quando yt-dlp mescla áudio+vídeo)
            elif info.get('requested_formats'):
                for fmt in info['requested_formats']:
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        stream_url = fmt['url']
                        break

            # 3) Lista de formats — pega o melhor áudio disponível
            elif info.get('formats'):
                audio_formats = [
                    f for f in info['formats']
                    if f.get('url') and f.get('acodec') not in (None, 'none')
                ]
                if not audio_formats:
                    audio_formats = [f for f in info['formats'] if f.get('url')]

                if audio_formats:
                    best = max(audio_formats, key=lambda f: f.get('abr') or f.get('tbr') or 0)
                    stream_url = best['url']

            if not stream_url:
                logging.error(f"Chaves retornadas pelo yt-dlp: {list(info.keys())}")
                raise ValueError(f"yt-dlp não retornou URL de stream para '{title}'")

        except Exception as e:
            logging.error(f"Erro ao obter stream de '{title}': {e}", exc_info=True)
            channel = guild.get_channel(MUSIC_CHANNEL_ID)
            if channel:
                await channel.send(f'❌ Erro ao carregar **{title}**, pulando...', delete_after=5)
            await self.play_next(guild)
            return

        source = FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=state['volume'])

        def after_playing(error):
            if error:
                logging.error(f'Erro durante reprodução: {error}')
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        vc.play(source, after=after_playing)
        await self.update_panel(guild)

    # ── Busca ─────────────────────────────────────────────────────────────────

    async def search_youtube(self, query: str, max_results: int = 5) -> list:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
            'max_downloads': max_results,
            'no_warnings': True,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(f'ytsearch{max_results}:{query}', download=False)
            )
            results = []
            for e in info.get('entries', []):
                # Constrói sempre a URL pelo ID para garantir URL válida
                video_id = e.get('id')
                url = f'https://www.youtube.com/watch?v={video_id}' if video_id else e.get('url', '')
                if url:
                    results.append({'url': url, 'title': e.get('title', 'Sem título')})
            return results

    def is_playlist(self, url: str) -> bool:
        return 'list=' in url or '/playlist' in url or '/sets/' in url

    def build_entry_url(self, entry: dict) -> str | None:
        entry_id = entry.get('id')
        entry_url = entry.get('url', '')
        if entry_url.startswith('http'):
            return entry_url
        if entry_id:
            return f'https://www.youtube.com/watch?v={entry_id}'
        return None

    # ── Handler de mensagens do canal ─────────────────────────────────────────

    async def handle_song_request(self, message: discord.Message):
        query = message.content.strip()
        guild = message.guild
        author = message.author
        channel = guild.get_channel(MUSIC_CHANNEL_ID)

        # Apaga a mensagem do usuário para manter o canal limpo
        try:
            await message.delete()
        except Exception:
            pass

        # Garante que o painel existe
        await self.get_or_create_panel(guild)

        # Usuário precisa estar em canal de voz
        if not author.voice or not author.voice.channel:
            if channel:
                await channel.send(
                    f'⚠️ {author.mention} Entre em um canal de voz primeiro!',
                    delete_after=6
                )
            return

        # Conecta ao canal de voz
        vc = guild.voice_client
        if not vc:
            vc = await author.voice.channel.connect()
        elif vc.channel != author.voice.channel:
            await vc.move_to(author.voice.channel)

        state = self.get_state(guild.id)

        # ── URL ──────────────────────────────────────────────────────────────
        if query.startswith(('http://', 'https://')):

            # Playlist
            if self.is_playlist(query):
                searching = await channel.send('📋 Carregando playlist, aguarde...', delete_after=15)
                try:
                    loop = asyncio.get_event_loop()
                    with yt_dlp.YoutubeDL(YDL_OPTS_PLAYLIST) as ydl:
                        info = await loop.run_in_executor(
                            None, lambda: ydl.extract_info(query, download=False)
                        )
                    if not info:
                        await channel.send('❌ Não foi possível acessar a playlist.', delete_after=8)
                        return

                    entries_raw = info.get('entries') or []
                    entries = [e for e in entries_raw if e]

                    if not entries:
                        await channel.send('❌ Playlist vazia ou sem músicas válidas.', delete_after=8)
                        return

                    added = 0
                    for entry in entries:
                        entry_url = self.build_entry_url(entry)
                        if not entry_url:
                            continue
                        entry_title = entry.get('title', 'Sem título')
                        state['queues'].append((entry_title, entry_url))
                        state['queue_titles'].append(entry_title)
                        added += 1

                    playlist_title = info.get('title', 'Playlist')
                    await channel.send(
                        f'✅ **{added}** músicas de **{playlist_title}** adicionadas à fila!',
                        delete_after=8
                    )
                except Exception as e:
                    logging.error(f'Erro ao carregar playlist: {e}', exc_info=True)
                    await channel.send(f'❌ Erro ao carregar playlist.', delete_after=8)
                    return

            # URL simples
            else:
                try:
                    loop = asyncio.get_event_loop()
                    with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                        info = await loop.run_in_executor(
                            None, lambda: ydl.extract_info(query, download=False)
                        )
                        title = info.get('title', 'Sem título')
                except Exception as e:
                    await channel.send(f'❌ Erro ao obter informações da URL.', delete_after=8)
                    return

                state['queues'].append((title, query))
                state['queue_titles'].append(title)

        # ── Pesquisa por texto ────────────────────────────────────────────────
        else:
            searching = await channel.send(f'🔍 Buscando **{query}**...', delete_after=10)
            results = await self.search_youtube(query)

            if not results:
                await channel.send('❌ Nenhum resultado encontrado.', delete_after=8)
                return

            first = results[0]

            # Se o resultado é óbvio, toca direto
            if len(results) == 1 or query.lower() in first['title'].lower():
                state['queues'].append((first['title'], first['url']))
                state['queue_titles'].append(first['title'])
            else:
                # Mostra menu de seleção com botões
                try:
                    await searching.delete()
                except Exception:
                    pass
                view = SearchView(results, self, guild, author.voice.channel)
                select_msg = await channel.send(
                    f'🔍 Resultados para **{query}** — selecione uma música:',
                    view=view,
                    delete_after=35
                )
                return  # Aguarda o callback do select

        # Toca se não houver música
        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(guild)
        else:
            await self.update_panel(guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
