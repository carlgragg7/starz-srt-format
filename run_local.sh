
# export KEY=transcribed_data/Pirates_of_the_Carribean/audio/Pirates_of_the_Carribean.mp3
# export KEY=raw_data/Amazon_Web_Service_and_VCCS_Cloud_Computing_Degree_Programs-20231114.mov
export KEY=raw_data/manhattan_tower_512kb.mp4
export BUCKET=cg-starz
export DESTINATION_FOLDER=PROCESSED-DATA

python3 -m src.main
# python3 src/main_new.py