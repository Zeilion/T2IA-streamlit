# ----------------------------------------------------------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------------------------------------------------------
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit_image_select import image_select
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import pandas as pd
import torch
import re
from libs.pipeline_YOLO import pipeline_yolo2
from libs.pipeline_GPT import *

#st.set_page_config(layout="wide")
# logos de la sidebar
#st.logo("pictures/logos/IDMC_LOGO_UL-02.png")

state = st.session_state
dict_lang = state.dict_lang[state.selected_lang]
# ----------------------------------------------------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------------------------------------------------
# 📂 Chemin vers le dossier d'images
IMAGE_FOLDER = Path(r"data/postcards_dataset_1024")  #TODO : possibilité de modifier le chemin du DataSet
img_list = list(IMAGE_FOLDER.rglob("*.jpg"))

# ⚙️ Paramètres
NUM_IMAGES = 12   # Nombre d'images

YOLO_DIR = Path(r"data/postmarks/model_det")
YOLO_SEG_DIR = Path(r"data/postmarks/model_seg")

# ----------------------------------------------------------------------------------------------------------------------
# Variables
# ----------------------------------------------------------------------------------------------------------------------
list_yolo_weights = list(YOLO_DIR.rglob('*.pt'))
list_yolo_seg_weights = list(YOLO_SEG_DIR.rglob('*.pt'))

dict_box_color = {
    0: 'red',
    1: 'yellow',
    2: 'blue',
    3: 'green',
    4: 'violet',
    5: 'white',
}

# ----------------------------------------------------------------------------------------------------------------------
# Fonctions
# ----------------------------------------------------------------------------------------------------------------------
def last_modif(list_file):
    """
    renvoie le dernier fichier modifié d'une liste de fichier
    :param list_file: liste de Path(fichier)
    :return: Path
    """
    last_file = list_file[0]
    last_mod = list_file[0].stat().st_mtime
    for file in list_file:
        if file.is_file():
            modif = file.stat().st_mtime
            if modif > last_mod:
                last_mod = modif
                last_file = file
    return last_file


def reload_gallery():
    state['selected_img_list'] = np.random.choice(img_list, size=NUM_IMAGES)


def run_pipelineYOLO2():
    state['res_pipeline'] = pipeline_yolo2(state['selected_img'],
                                                      state['yolo_path'],
                                                      state['yolo_seg_path']).T[0]


def change_coord(bbox):
    """Modifie l'ordre des coordonnées des bbox"""
    x_min, x_max, y_min, y_max = bbox
    return [x_min, y_min, x_max, y_max]

# ----------------------------------------------------------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------------------------------------------------------
# Initialiser l'état de l'application si non défini
if 'selected_img_list' not in state:
    state['selected_img_list'] = np.random.choice(img_list, size=NUM_IMAGES)
if 'selected_img' not in state:
    state['selected_img'] = None
if 'yolo_path' not in state:
    state['yolo_path'] = last_modif(list_yolo_weights)
if 'yolo_seg_path' not in state:
    state['yolo_seg_path'] = last_modif(list_yolo_seg_weights)
if 'res_pipeline' not in state:
    state['res_pipeline'] = None
if 'res_gpt4' not in state:
    state['res_gpt4'] = None
if 'gpt_responses' not in state:
    gpt_responses = pd.read_csv(Path(r"data/postmarks/ft150GPT4o_1155stamps.csv"))
    gpt_responses['stamp'] = gpt_responses['stamp'].map(lambda x: x.replace('_cls1', ''))
    gpt_responses.set_index('stamp', drop=True, inplace=True)
    state['gpt_responses'] = gpt_responses

    # mise à jour de l'url avec la langue
    if "selected_lang" in state:
        st.query_params['lang'] = state["selected_lang"]
    else:
        st.query_params['lang'] = "fr"

    st.rerun()

# ----------------------------------------------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------------------------------------------
# 🖼️ Affichage
st.title(dict_lang["4-pipeline"])

gallery_cols = st.columns([0.8, 0.2])

with gallery_cols[0]:
    st.subheader(f"🖼️ {dict_lang["4-gallery"]}")

with gallery_cols[-1]:
    st.button(dict_lang["4-reload"], on_click=reload_gallery, use_container_width=True)

with st.container(border=True):
    img_path = image_select(dict_lang["choose_image"], state['selected_img_list'])


if state['selected_img'] is not img_path:
    state['selected_img'] = img_path
    state['res_pipeline'] = None
    state['res_gpt4'] = None


pipeline_cols = st.columns([0.25, 0.75])

with pipeline_cols[0]:
    with st.container(border=True):
        with st.container(border=True):
            st.markdown(dict_lang["selected_image"])
            st.image(img_path, caption=img_path.stem, use_container_width=True)

        with st.container(border=True):
            st.markdown(dict_lang["4-pipeline_params"])
            dict_yolo_det = {
                path: path.stem.split('-')[-1].split('_')[0].capitalize() for path in list_yolo_weights
            }
            st.selectbox(
                dict_lang["4-det_model"],
                dict_yolo_det,
                format_func=lambda x: dict_yolo_det[x],
                key='yolo_path',
            )

            dict_yolo_seg = {
                path: path.stem.split('_')[0].split('e-')[-1].capitalize() for path in list_yolo_seg_weights
            }
            st.selectbox(
                dict_lang["4-seg_model"],
                dict_yolo_seg,
                format_func=lambda x: dict_yolo_seg[x],
                key='yolo_seg_path',
            )


        st.button(dict_lang["4-run"], on_click=run_pipelineYOLO2, use_container_width=True)


with pipeline_cols[1]:
    with st.container(border=True):
        if state['res_pipeline'] is not None:
            if state['res_pipeline']['boxes_cls'].shape[0] == 0:

                def draw_no_boxes(img_path):
                    img_with_boxes = Image.open(img_path)
                    draw = ImageDraw.Draw(img_with_boxes)
                    text = "[PAS DE DETECTION]"
                    text_color = (200, 0, 0)
                    # Calculate the position to center the text
                    x = img_with_boxes.width / 2
                    y = img_with_boxes.height / 2

                    draw.text((x, y), text, align='center', anchor='mm', fill=text_color, font_size=256)
                    return img_with_boxes

                # Affichage de l'image avec les bounding boxes
                image_no_boxes = draw_no_boxes(img_path)
                st.image(image_no_boxes, use_container_width=True)

            else:
                def draw_bounding_boxes(img_path, res_df):
                    img_with_boxes = Image.open(img_path)
                    draw = ImageDraw.Draw(img_with_boxes)
                    for cls, box in zip(res_df['boxes_cls'], res_df['boxes_adj']):
                        draw.rectangle(box.tolist(), outline=dict_box_color[cls], width=2)  # 10 pour img originales
                    return img_with_boxes

                # Affichage de l'image avec les bounding boxes
                image_with_boxes = draw_bounding_boxes(img_path, state['res_pipeline'])
                st.image(image_with_boxes, use_container_width=True)


if state['res_pipeline'] is not None:
    if state['res_pipeline']['boxes_cls'].shape[0] != 0:
        # si on détecte des tampons
        stamps_idx = (state['res_pipeline']['boxes_cls'] == 1)
        if (state['res_pipeline']['boxes_cls'] == 1).sum() > 0:
            stamps_list = state['res_pipeline']['stamps_bins'][stamps_idx].tolist()
            stamps_titles = state['res_pipeline']['stamps_titles'][stamps_idx].tolist()

            with st.expander(dict_lang["4-detected_stamp"]):
                st.warning(dict_lang["4-nb"])
                stamps_cols = st.columns([0.2, 0.8])

                with stamps_cols[0]:
                    with st.container(border=True):
                        stamp_idx = image_select(dict_lang["4-choose_stamp"], stamps_list, return_value='index')
                        stamp_img = stamps_list[stamp_idx]
                        stamps_title = stamps_titles[stamp_idx]

                with stamps_cols[1]:

                    stamps_sub_cols = st.columns([0.5, 0.5])

                    with stamps_sub_cols[0]:
                        st.image(stamp_img * 255, use_container_width=True, caption=stamps_title)

                        with stamps_sub_cols[1]:
                            with st.container(border=True):
                                st.markdown(dict_lang["4-gpt_reading"])

                                if stamps_title in state['gpt_responses'].index:
                                    processed_resp = state['gpt_responses'].loc[stamps_title, :]
                                else:
                                    processed_resp = pd.Series(
                                        json.loads(empty_json(stamps_title))
                                    ).rename(index=stamps_title).drop('stamp')

                                # traduction pour affichage
                                processed_resp.rename(index=dict_lang, inplace=True)
                                processed_resp = processed_resp.map(lambda x: dict_lang[str(x)] if str(x) in dict_lang else x)

                                st.dataframe(processed_resp, use_container_width=True)

                        #if st.button("Envoyer à GPT", use_container_width=True):
                        #    with stamps_sub_cols[1]:
                        #        with st.container(border=True):
                        #            with st.spinner(text="Envoi à GPT4o...", show_time=True):

                        #                stamp_base64 = img_array_to_base64(stamp_img)

                        #                gpt_resp = get_GPT_response(stamp_base64,
                        #                                            stamps_title,
                        #                                            system_content,
                        #                                            model=GPT_MODEL)

                        #                processed_resp = process_GPT4_response(gpt_resp, stamps_title)
                        #                processed_resp = processed_resp.rename(index=processed_resp.stamp).drop('stamp')

                        #            st.markdown("Lecture de GPT4o :")
                        #            st.dataframe(processed_resp, use_container_width=True)


# détection de fin de chargement de la page
if ("pipeline_init" not in state) or not state.pipeline_init:
    state["home_init"] = False
    state["map_init"] = False
    state["research_init"] = False
    state["pipeline_init"] = True
    # mise à jour de l'url avec la langue (obligé sinon clic en plus requis pour map notament)
    if "selected_lang" in state:
        st.query_params['lang'] = state["selected_lang"]
    else:
        st.query_params['lang'] = "fr"

    st.rerun()