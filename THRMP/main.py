import sys
import os
import random
import wave
import pyaudio
import numpy as np
from time import sleep
from typing import Union
import threading
import miniaudio
import customtkinter as ctk
import time
from PIL import Image, ImageTk
from pathlib import Path
import json
from random import choice
from glob import glob
import math

class Sound():
    def __init__(self, filename: str):
        dec = miniaudio.decode_file(filename, output_format = miniaudio.SampleFormat.SIGNED16)
        self.samples = dec.samples
        self.nchannels = dec.nchannels
        self.sample_rate = dec.sample_rate

        self.audio_bytes = self.samples.tobytes()
        self.sample_width = 2
        self.bytes_per_frame = self.nchannels * self.sample_width
        self.nframes = len(self.samples) // self.nchannels
        self.chunk_size = 1024 * self.bytes_per_frame

        self.current_position = 0
        self.total_duration = self.nframes / self.sample_rate
    
    def read_frames(self, num_frames: int = 1024):
        byte_count = num_frames * self.bytes_per_frame
        data_chunk = self.audio_bytes[self.current_position:self.current_position + byte_count]
        self.current_position += byte_count
        return data_chunk

    def getnframes(self): return self.nframes
    def getnchannels(self): return self.nchannels
    def getframerate(self): return self.sample_rate
    def getsamplewidth(self): return self.sample_width
    def tell(self): return self.current_position
    def set_pos(self, pos): self.current_position = pos


    



class CommandHandler():
    def __init__(self):
        # States
        self.is_playing = False

        # Flags
        self.start_new = False
        self.do_replay = False
        self.is_pausing = False
        self.is_unpausing = False
        self.update_config = False

        # Vars
        self.current_track = ""
        self.current_album = ""
        self.current_album_short = ""
        self.current_track_work_order = None
        self.play_pause_text = "Play"
        self.play_pause_color = "#3B9940"
        self.replay_text = "Replay Current Track"
        self.replay_color = "#3B9940"
        self.current_playback_progress = 0.0
        self.current_album_image = f"{file_dir}/Placeholder.png"
        self.current_track_total_duration = 1.0
        self.seek_dist = 0
        self.seek_ratio = 0
        self.track_change = 0
        self.track_change_val = 0

    def play_button_toggle(self):
        if self.is_playing:
            self.is_playing = False
            self.is_pausing = True
            self.play_pause_text = "Play"
            self.play_pause_color = "#3B9940"
        else:
            self.is_playing = True
            self.is_unpausing = True
            self.play_pause_text = "Pause"
            self.play_pause_color = "#62130D"
            if self.current_track == "":
                self.track_change = 1
    
    def replay_button_toggle(self):
        if self.do_replay:
            self.do_replay = False
            self.replay_text = "Replay Current Track"
            self.replay_color = "#3B9940"
        else:
            self.do_replay = True
            self.replay_text = "Stop Replaying"
            self.replay_color = "#62130D"
    
    def next_track(self):
        self.track_change = "relative"
        self.track_change_val = 1

    def previous_track(self):
        self.track_change = "relative"
        self.track_change_val = -1

    def send(self, command, val):
        if debug:
            print(f"Set {command}: {val}")
        setattr(self, command, val)

    def read(self, command):
        val = getattr(self, command)
        if debug:
            print(f"Read {command}: {val}")
        return val

    def set_flag(self, command):
        if debug:
            print(f"Set flag {command}")
        setattr(self, command, True)

    def consume_flag(self, command):
        val = getattr(self, command)
        if debug:
            print(f"Consume {command}: {val}")
        if val == True:
            setattr(self, command, False)
        return val
    
    def consume_val(self, command):
        val = getattr(self, command)
        if val != 0:
            setattr(self, command, 0)
        return val
    

class PlaylistHandler():
    def __init__(self):
        self.current_order = 0
        self.current_id = None
        self.current_playlist = []
        self.available = []
        self.playlist_frame: Union[PlaylistFrame, None] = None
        self.info_frame: Union[InfoSubframe, None] = None
    
    def read(self, command):
        val = getattr(self, command)
        if debug:
            print(f"Read {command}: {val}")
        return val

    def load_avail(self) -> list:
        track_data_path = f"{file_dir}/track_data.json"
        temp_tracklist = []

        with open(track_data_path, encoding = "utf-8") as J:
            data = json.load(J)
        
        for k in data.keys():
            temp_tracklist.append(k)
        
        return temp_tracklist

    def load_all(self) -> dict:
        track_data_path = f"{file_dir}/track_data.json"

        with open(track_data_path, encoding = "utf-8") as J:
            data = json.load(J)
        
        return data

    def load_data(self, track_id: str) -> dict:
        track_data_path = f"{file_dir}/track_data.json"

        with open(track_data_path, encoding = "utf-8") as J:
            data = json.load(J)
        
        return data[track_id]

    def pick_rand(self, repeats: bool) -> str:
        selection = choice(self.available)
        if (not repeats) and (selection in self.current_playlist):
            selection = self.pick_rand(repeats)
        return selection

    def start_new(self, cfg : dict, **kwargs) -> list[str, dict]:
        #print(self.current_order, self.current_playlist)
        if ("order" in kwargs.keys()) or ("relative" in kwargs.keys()):
            if "order" in kwargs.keys():
                self.current_order = kwargs["order"]
            
            elif "relative" in kwargs.keys():
                self.current_order = self.current_order + kwargs["relative"]
                if self.current_order <= -1:
                    self.current_order = 0
            
            if self.current_order in list(range(len(self.current_playlist))):
                self.current_id = self.current_playlist[self.current_order]
            else:
                if len(self.current_playlist) == len(self.available):
                    self.current_playlist = []
                    self.playlist_frame.wipe_tracklist()
                if cfg["random"]:
                    self.current_id = self.pick_rand(cfg["allow_repeats"])
                    self.current_order = len(self.current_playlist)
                    self.current_playlist.append(self.current_id)
                else:
                    self.current_id += 1
                    self.current_order = len(self.current_playlist)
                    self.current_playlist.append(self.current_id)
                self.playlist_frame.add_track_to_list(self.current_id)

        
        elif "track_id" in kwargs.keys():
            self.current_id = kwargs["track_id"]
            if kwargs["track_id"] not in self.current_playlist:
                self.current_order = len(self.current_playlist)
                self.current_playlist.append(self.current_id)
                self.playlist_frame.add_track_to_list(self.current_id)
                
            else:
                self.current_order = self.current_playlist.index(self.current_id)
        
        else:
            if len(self.current_playlist) == len(self.available):
                self.current_playlist = []
                self.playlist_frame.wipe_tracklist()
            if cfg["random"]:
                self.current_id = self.pick_rand(cfg["allow_repeats"])
                self.current_order = len(self.current_playlist)
                self.current_playlist.append(self.current_id)
            else:
                self.current_id += 1
                self.current_order = len(self.current_playlist)
                self.current_playlist.append(self.current_id)
            self.playlist_frame.add_track_to_list(self.current_id)

        track_data = self.load_data(self.current_id)
        self.info_frame.display_info(self.current_id, track_data)
        return self.current_id, track_data
    
    def album_image(self, work_abr: str) -> str:
        selection = ""
        files = glob(f"{file_dir}/AlbumImages/*")
        for file in files:
            if file.split("\\")[-1].split(".")[0] == work_abr:
                selection = file
                break
        
        return selection





class App(ctk.CTk):
    def __init__(self, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__()
        self.title("Touhou Random Music Player")
        self.geometry("1920x1080")
        self.configure(fg_color = "#3B8A40")
        self.CH = CH
        self.PH = PH

        self.grid_columnconfigure(tuple(np.arange(0, 11)), weight = 1)
        self.grid_rowconfigure(tuple(np.arange(0, 11)), weight = 1)
        
        self.player_frame = PlayerFrame(self, CH, PH)
        self.player_frame.configure(border_color = "#3B8A40", border_width = 5, fg_color = "#3B6740", corner_radius = 25)
        self.player_frame.grid(row = 0, column = 2, columnspan = 2, rowspan = 7, sticky = "nsew")

        self.playlist_frame = PlaylistTabview(self, CH, PH)
        self.playlist_frame.configure(border_color = "#3B8A40", border_width = 5, fg_color = "#3B6740", corner_radius = 25, segmented_button_fg_color = "#3B6740", segmented_button_unselected_color = "#3B7D40", segmented_button_selected_color = "#3B9940", segmented_button_selected_hover_color = "#3B9940")
        self.playlist_frame.grid(row = 0, column = 4, columnspan = 4, rowspan = 11, sticky = "nsew")

        self.ranking_frame = RankingFrame(self, CH, PH)
        self.ranking_frame.configure(border_color = "#3B8A40", border_width = 5, fg_color = "#3B6740", corner_radius = 25)
        self.ranking_frame.grid(row = 0, column = 8, columnspan = 4, rowspan = 11, sticky = "nsew")

        self.info_frame = InfoFrame(self, CH, PH)
        self.info_frame.configure(border_color = "#3B8A40", border_width = 5, fg_color = "#3B6740", corner_radius = 25)
        self.info_frame.grid(row = 7, column = 2, columnspan = 2, rowspan = 4, sticky = "nsew")

        self.config_frame = ConfigFrame(self, CH, PH)
        self.config_frame.configure(border_color = "#3B8A40", border_width = 5, fg_color = "#3B6740", corner_radius = 25)
        self.config_frame.grid(row = 0, column = 0, columnspan = 2, rowspan = 11, sticky = "nsew")
        
        self.after(100, self.update)
    
    def update(self):
        if self.CH.is_playing:
            self.title(f"Touhou Random Music Player : {self.CH.current_album_short} #{self.CH.current_track_work_order} - {self.CH.current_track}")
        else:
            self.title("Touhou Random Music Player")
        self.player_frame.current_playing_frame.album_image.configure(light_image = ImgResize(self.CH.current_album_image, (400, 400))[0], size = ImgResize(self.CH.current_album_image, (400, 400))[1])
        self.player_frame.current_playing_frame.current_track_label.configure(text = self.CH.current_track)
        self.player_frame.current_playing_frame.current_album_label.configure(text = self.CH.current_album)
        self.player_frame.elapsed_time_label.configure(text = f"{math.floor(divmod(self.CH.current_track_total_duration*self.CH.current_playback_progress, 60)[0]):02d}:{math.floor(divmod(self.CH.current_track_total_duration*self.CH.current_playback_progress, 60)[1]):02d}")
        self.player_frame.total_time_label.configure(text = f"{math.floor(divmod(self.CH.current_track_total_duration, 60)[0]):02d}:{math.floor(divmod(self.CH.current_track_total_duration, 60)[1]):02d}")
        self.player_frame.play_button.configure(text = self.CH.play_pause_text, fg_color = self.CH.play_pause_color)
        self.player_frame.replay_button.configure(text = self.CH.replay_text, fg_color = self.CH.replay_color)
        self.player_frame.track_progress_bar.set(self.CH.read("current_playback_progress"))

        self.after(100, self.update)


class PlayerFrame(ctk.CTkFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)
        self.CH = CH
        self.PH = PH

        self.grid_columnconfigure(tuple(np.arange(0, 6)), weight = 1)
        self.grid_rowconfigure(tuple(np.arange(0, 8)), weight = 1)
        self.grid_rowconfigure(tuple(np.arange(0, 4)), weight = 10)
        self.grid_rowconfigure(5, weight = 0)

        self.current_playing_frame = CurrentDisplayFrame(self, CH)
        self.current_playing_frame.configure(border_color = "#1E351A", border_width = 2, fg_color = "#CEFEC0", corner_radius = 5)
        self.current_playing_frame.grid(row = 0, column = 0, columnspan = 6, rowspan = 5, padx = 15, pady = 15, sticky = "nsew")

        self.track_progress_bar = ctk.CTkProgressBar(self, width = 0, height = 10, corner_radius = 5, border_color = "#1E351A", border_width = 2, fg_color = "#1E351A", progress_color = "red", orientation = "horizontal", mode = "determinate")
        self.track_progress_bar.grid(row = 5, column = 1, columnspan = 4, padx = 5, pady = 5, sticky = "ew")
        self.track_progress_bar.bind("<Button-1>", self.on_progress_click)

        self.elapsed_time_label = ctk.CTkLabel(self, text = f"{math.floor(divmod(self.CH.current_track_total_duration*self.CH.current_playback_progress, 60)[0]):02d}:{math.floor(divmod(self.CH.current_track_total_duration*self.CH.current_playback_progress, 60)[1]):02d}", width = 0, height = 0)
        self.elapsed_time_label.grid(row = 5, column = 0, padx = 12, pady = 5, sticky = "nsew")

        self.total_time_label = ctk.CTkLabel(self, text = f"{math.floor(divmod(self.CH.current_track_total_duration, 60)[0]):02d}:{math.floor(divmod(self.CH.current_track_total_duration, 60)[1]):02d}", width = 0, height = 0)
        self.total_time_label.grid(row = 5, column = 5, padx = 12, pady = 5, sticky = "nsew")

        self.play_button = ctk.CTkButton(self, width = 0, height = 0, text=self.CH.play_pause_text, command=self.CH.play_button_toggle, fg_color = self.CH.play_pause_color, border_color = "#0F120D", border_width = 2)
        self.play_button.grid(row = 6, column = 2, columnspan = 2, padx = 5, pady = 5, sticky = "nsew")

        self.seek_back_button = ctk.CTkButton(self, width = 0, height = 0, text="-10s", command=lambda: self.CH.send("seek_dist", -10), fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.seek_back_button.grid(row = 6, column = 1, padx = 5, pady = 5, sticky = "nsew")

        self.seek_forward_button = ctk.CTkButton(self, width = 0, height = 0, text="+10s", command=lambda: self.CH.send("seek_dist", 10), fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.seek_forward_button.grid(row = 6, column = 4, padx = 5, pady = 5, sticky = "nsew")

        self.seek_back_far_button = ctk.CTkButton(self, width = 0, height = 0, text="-30s", command=lambda: self.CH.send("seek_dist", -30), fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.seek_back_far_button.grid(row = 7, column = 1, padx = 5, pady = (5, 10), sticky = "nsew")

        self.seek_forward_far_button = ctk.CTkButton(self, width = 0, height = 0, text="+30s", command=lambda: self.CH.send("seek_dist", 30), fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.seek_forward_far_button.grid(row = 7, column = 4, padx = 5, pady = (5, 10), sticky = "nsew")

        self.previous_track_button = ctk.CTkButton(self, width = 0, height = 0, text="Prev", command=self.CH.previous_track, fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.previous_track_button.grid(row = 6, column = 0, padx = (10, 5), pady = 5, sticky = "nsew")

        self.next_track_button = ctk.CTkButton(self, width = 0, height = 0, text="Next", command=self.CH.next_track, fg_color = "#3B7D40", border_color = "#0F120D", border_width = 2)
        self.next_track_button.grid(row = 6, column = 5, padx = (5, 10), pady = 5, sticky = "nsew")

        self.replay_button = ctk.CTkButton(self, width = 0, height = 0, text=self.CH.replay_text, command=self.CH.replay_button_toggle, fg_color = self.CH.replay_color, border_color = "#0F120D", border_width = 2)
        self.replay_button.grid(row = 7, column = 2, columnspan = 2, padx = 5, pady = (5, 10), sticky = "nsew")

    def on_progress_click(self, event):
        widget_width = self.track_progress_bar.winfo_width()
        click_x = event.x
        new_value = max(0.0, min(1.0, click_x / widget_width))
        self.CH.send("seek_ratio", new_value + 1)

class CurrentDisplayFrame(ctk.CTkFrame):
    def __init__(self, master, CH: CommandHandler):
        super().__init__(master)
        self.CH = CH

        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(tuple(np.arange(0, 5)), weight = 1)

        self.album_image = ctk.CTkImage(light_image = ImgResize(self.CH.current_album_image, (400, 400))[0], size = ImgResize(self.CH.current_album_image, (400, 400))[1])
        self.album_image_label = ctk.CTkLabel(self, text = "", image = self.album_image, height = 400, width = 400)
        self.album_image_label.grid(row = 0, column = 0, rowspan = 3, padx = 4, pady = (12,5), sticky = "nsew")

        self.current_album_label = ctk.CTkLabel(self, text = self.CH.current_album, width = 0, height = 0, font = ("Arial", 12))
        self.current_album_label.grid(row = 3, column = 0, padx = 12, pady = (5, 0), sticky = "nsew")

        self.current_track_label = ctk.CTkLabel(self, text = self.CH.current_track, width = 600, height = 0, font = ("Helvetica", 20, "bold"))
        self.current_track_label.grid(row = 4, column = 0, padx = 12, pady = (0, 15), sticky = "nsew")

class PlaylistTabview(ctk.CTkTabview):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)

        self.playlist_tab = self.add("Playlist")
        self.all_tracks_tab = self.add("All Tracks")

        self.playlist_tab.grid_columnconfigure(0, weight = 1)
        self.playlist_tab.grid_rowconfigure(0, weight = 1)

        self.all_tracks_tab.grid_columnconfigure(0, weight = 1)
        self.all_tracks_tab.grid_rowconfigure(0, weight = 1)

        self.playlist_frame = PlaylistFrame(self.playlist_tab, CH, PH)
        self.playlist_frame.grid(row = 0, column = 0, padx = 0, pady = 0, sticky = "nsew")
        self.playlist_frame.configure(border_color = "#1E351A", border_width = 2, fg_color = "#CEFEC0")

        self.all_tracks_frame = TracksFrame(self.all_tracks_tab, CH, PH)
        self.all_tracks_frame.grid(row = 0, column = 0, padx = 0, pady = 0, sticky = "nsew")
        self.all_tracks_frame.configure(border_color = "#1E351A", border_width = 2, fg_color = "#CEFEC0")

class PlaylistFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)
        self.CH = CH
        self.PH = PH
        self.PH.playlist_frame = self
        self.num = 0

        self.grid_columnconfigure(0, weight = 1)

        #self.after(100, self.update)
    
    def update(self):

        self.after(100, self.update)

    def add_track_to_list(self, track_id):
        self.grid_rowconfigure(self.num, weight = 1)
        track_data = self.PH.load_data(track_id)

        if track_data["prefix_abr"] is not None:
            top = f"{track_data['prefix_abr']} {track_data['en_work']} #{track_data['work_order']}"
        else:
            top = f"{track_data['en_work']} #{track_data['work_order']}"
        bottom = f"{track_data['en_name']}"

        label = ctk.CTkLabel(self, width = 0, height = 32, text = f"{top}\n{bottom}", font = ("Arial", 10))
        label.bind("<Button-1>", lambda event, track_id = track_id: track_change_id(track_id, self.CH))
        label.bind("<Enter>", lambda event, label = label: label.configure(fg_color = "#A6FE8E", cursor = "hand2"))
        label.bind("<Leave>", lambda event, label = label : label.configure(fg_color = "#CEFEC0", cursor = ""))
        label.grid(row = self.num, column = 0, padx = 0, pady = 0, sticky = "nsew")
        self.num += 1
    
    def wipe_tracklist(self):
        for widget in self.winfo_children():
            widget.destroy()

class TracksFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)
        self.CH = CH
        self.PH = PH

        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(tuple(np.arange(0, len(self.PH.available))), weight = 1)

        for i, (track_id, track_data) in enumerate(self.PH.load_all().items()):

            if track_data["prefix_abr"] is not None:
                top = f"{track_data['prefix_abr']} {track_data['en_work']} #{track_data['work_order']}"
            else:
                top = f"{track_data['en_work']} #{track_data['work_order']}"
            bottom = f"{track_data['en_name']}"

            label = ctk.CTkLabel(self, width = 0, height = 32, text = f"{top}\n{bottom}", font = ("Arial", 10))
            label.bind("<Button-1>", lambda event, track_id = track_id: track_change_id(track_id, CH))
            label.bind("<Enter>", lambda event, label = label: label.configure(fg_color = "#A6FE8E", cursor = "hand2"))
            label.bind("<Leave>", lambda event, label = label : label.configure(fg_color = "#CEFEC0", cursor = ""))
            label.grid(row = i, column = 0, padx = 0, pady = 0, sticky = "nsew")

class RankingFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)

class InfoFrame(ctk.CTkFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)
        self.CH = CH
        self.PH = PH

        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(0, weight = 1)

        self.subframe = InfoSubframe(self, CH, PH)
        self.subframe.grid(row = 0, column = 0, padx = 15, pady = 15, sticky = "nsew")
        self.subframe.configure(border_color = "#1E351A", border_width = 2, fg_color = "#CEFEC0")
        
class InfoSubframe(ctk.CTkScrollableFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)
        self.CH = CH
        self.PH = PH
        self.PH.info_frame = self

        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(0, weight = 1)

        self.label = ctk.CTkLabel(self, width = 0, height = 0, text = f"", font = ("Helvetica", 15, "bold"), text_color = "black", anchor = "nw", justify = "left")
        self.label.grid(row = 0, column = 0, padx = 10, pady = 10, sticky = "nsew")

    def display_info(self, track_id, track_data):

        label_text = f"Track ID: {track_id}\nEnglish Track Name: {track_data['en_name']}"
        if (track_data['jp_work_prefix'] is not None) and (track_data['jp_work'] is not None):
            label_text += f"\nFrom: {track_data['jp_work_prefix']} ~ {track_data['jp_work']}"
            label_text += f"\n           {track_data['rj_work_prefix']} ~ {track_data['rj_work']}"
            label_text += f"\n           {track_data['en_work_prefix']} ~ {track_data['en_work']}"
        elif (track_data['en_work_prefix'] is not None) and (track_data['jp_work'] is not None):
            label_text += f"\nFrom: {track_data['en_work_prefix']} ~ {track_data['jp_work']}"
            label_text += f"\n           {track_data['en_work_prefix']} ~ {track_data['rj_work']}"
            label_text += f"\n           {track_data['en_work_prefix']} ~ {track_data['en_work']}"
        elif (track_data['en_work_prefix'] is not None):
            label_text += f"\nFrom: {track_data['en_work_prefix']} ~ {track_data['en_work']}"
        else:
            label_text += f"\nFrom: {track_data['en_work']}"
        label_text += f"\nTrack Number: {track_data['work_order']}"
        if (track_data['place'] is not None):
            label_text += f"\nPlays For: {track_data['place']}"
        label_text += f"\nReleased On: {track_data['release_date']}"
        label_text += f"\nComposed By: {track_data['composer']}"


        self.label.configure(text = label_text)

class ConfigFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, CH: CommandHandler, PH: PlaylistHandler):
        super().__init__(master)


def track_change_id(track_id: str, CH: CommandHandler):
    CH.send("track_change", "track_id")
    CH.send("track_change_val", track_id)


def track_change(PAengine: pyaudio.PyAudio, CH: CommandHandler, PH: PlaylistHandler, cfg: dict, mode: Union[str, int], val: int):

    if mode == "relative":
        track_id, track_data = PH.start_new(cfg, relative = val)
    elif mode == "order":
        track_id, track_data = PH.start_new(cfg, order = val)
    elif mode == "track_id":
        track_id, track_data = PH.start_new(cfg, track_id = val)
    else:
        track_id, track_data = PH.start_new(cfg)

    album_image = PH.album_image(track_data["work_abr"])

    CH.send("current_track", f"{track_data['en_name']}")
    if track_data['prefix_abr'] is not None:
        CH.send("current_album", f"{track_data['prefix_abr']} - {track_data['en_work']} - Track #{track_data['work_order']}")
        CH.send("current_album_short", f"{track_data['prefix_abr']} - {track_data['work_abr']}")
    else:
        CH.send("current_album", f"{track_data['en_work']} - Track #{track_data['work_order']}")
        CH.send("current_album_short", f"{track_data['work_abr']}")
    CH.send("current_track_work_order", track_data['work_order'])
    CH.send("current_album_image", f"{album_image}")

    file = Sound(f"{file_dir}/Music/{track_id}.mp3")
    stream = PAengine.open(format = PAengine.get_format_from_width(file.getsamplewidth()), channels = file.getnchannels(), rate = file.getframerate(), output = True, output_device_index = output_device)

    return file, stream


def audio_handler(app: App, CH: CommandHandler, PH: PlaylistHandler, audio_kill: threading.Event):
    
    PAengine = pyaudio.PyAudio()
    cfg = read_config()
    file = None

    while app.winfo_exists():
        #print(PH.read("current_order"), PH.read("current_id"), CH.read("current_track"))

        if CH.consume_flag("update_config"):
            cfg = read_config()

        if CH.read("track_change"):
            mode = CH.consume_val("track_change")
            val = CH.consume_val("track_change_val")

            file, stream = track_change(PAengine, CH, PH, cfg, mode, val)
        
        if file is not None:
            CH.send("current_track_total_duration", file.total_duration)
            if CH.read("seek_ratio"):
                ratio = CH.consume_val("seek_ratio")
                file.set_pos((math.floor(np.clip(ratio - 1, 0, 1) * (file.nframes * file.bytes_per_frame)) // 1024) * 1024)
            if CH.read("seek_dist"):
                dist = CH.consume_val("seek_dist")
                file.set_pos(np.clip(file.tell() + (file.getframerate() * file.getsamplewidth() * file.getnchannels() * dist), 0, file.nframes * file.bytes_per_frame))
            CH.send("current_playback_progress", file.tell()/(file.nframes * file.bytes_per_frame))
        else:
            CH.consume_val("seek_dist")
            CH.consume_val("seek_ratio")

        if CH.is_playing:
            data = file.read_frames(1024)
            
            if not ((len(data) == 0)) or (file.tell() == file.getnframes()):
                stream.write(data)
            else:
                if CH.read("do_replay"):
                    file.set_pos(0)
                else:
                    CH.send("track_change", "relative")
                    CH.send("track_change_val", 1)

def read_config() -> dict:
    return {"random": True, "allow_repeats": False}

def ImgResize(image_path : str, target_dim : tuple):
    preview_image = Image.open(image_path)#.convert("RGBA")

    w, h = preview_image.size
    i_ratio = w / h

    tw, th = target_dim

    t_ratio = tw / th

    h_ratio = th / h

    w_ratio = tw / w

    if i_ratio < t_ratio:
        r_w = round(w * h_ratio)
        r_h = round(h * h_ratio)
        #r_w = tw
        #r_h = round(tw * (1 / i_ratio))
    else:
        r_w = round(w * w_ratio)
        r_h = round(h * w_ratio)
        #r_h = th
        #r_w = round(th * i_ratio)
    preview_image = preview_image.resize((r_w, r_h), Image.Resampling.BICUBIC)

    return preview_image, (r_w, r_h)

def quit_program(window: App, audio_kill: threading.Event):
    audio_kill.set()
    window.destroy()
    sys.exit()

if __name__ == "__main__":
    debug = False
    file_dir = Path(__file__).resolve().parent
    output_device = pyaudio.PyAudio().get_default_output_device_info()["index"]
    
    commands = CommandHandler()
    playlist = PlaylistHandler()
    playlist.available = playlist.load_avail()

    app = App(commands, playlist)
    app.resizable(False, False)
    icon_image, icon_size = ImgResize(f"{file_dir}/Placeholder.png", (128, 128))
    icon = ImageTk.PhotoImage(icon_image, icon_size)
    app.iconphoto(True, icon)
    
    audio_kill = threading.Event()
    audio_thread = threading.Thread(target = audio_handler, args = (app, commands, playlist, audio_kill), daemon = True)
    commands.send("audio_thread", audio_thread)
    audio_thread.start()

    app.protocol("WM_DELETE_WINDOW", lambda: quit_program(app, audio_kill))
    app.mainloop()