from fitbit import gather_keys_oauth2 as Oauth2
import fitbit
from dateutil import parser
import pandas as pd 
import numpy as np
import altair as alt
from datetime import timedelta
from datetime import datetime
import seaborn as sns
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter


# CLIENT FUNCTIONS
def authenticate(client_id:str, client_secret:str):
    server = Oauth2.OAuth2Server(client_id, client_secret)

    server.browser_authorize()

    access_token = str(server.fitbit.client.session.token['access_token'])
    refresh_token = str(server.fitbit.client.session.token['refresh_token'])

    return access_token, refresh_token


def build_client(access_token:str, refresh_token:str) -> fitbit.api.Fitbit:
    return fitbit.Fitbit(CLIENT_ID,
                         CLIENT_SECRET, 
                         oauth2 = True,
                         access_token = access_token,
                         refresh_token = refresh_token)


def display_auth_status(state):
    if state == True:
        st.sidebar.success(f"Authenticated. Using API version {st.session_state.client.API_VERSION}")
    if state == False:
        st.sidebar.warning(f"Not authenticated with Fitbit API.")


# FETCH DATA
@st.cache()
def get_user_data(client):
    return client.user_profile_get()["user"]


@st.cache()
def get_sleep_data(client, date):
    return client.get_sleep(date)


@st.cache()
def get_heart_data(client, date):
    return client.time_series(resource = 'activities/heart', 
                              period='1d', 
                              base_date=date)


# FORMATTING FUNCTIONS
def format_dob(dob):
    return datetime.strftime(datetime.strptime(dob, '%Y-%m-%d'), "%d/%m/%Y")


def format_sleep_time_limits(zoned_datetime):
    #return datetime.datetime.strftime(datetime.datetime.strptime(parser.parse(zoned_datetime), '%Y-%m-%d %H:%M:%S'), '%d-%m-%Y')
    return parser.parse(zoned_datetime)


def format_time_in_stage(time_format:str, time_in_stage:int) -> str:
    return time_format.format(*divmod(time_in_stage, 60))


def calc_percentage(minutes_in_stage:int, minutes_in_bed:int) -> int:
    return round((minutes_in_stage / minutes_in_bed) * 100)


def get_30_day_avg(sleep_stage:str) -> int:
    return sleep_data['sleep'][0]['levels']['summary'][sleep_stage]['thirtyDayAvgMinutes']


# PLOTTING FUNCTIONS
def plot_stage_summary(source:pd.DataFrame):
    stage_summary_chart = alt.Chart(source).transform_joinaggregate(
                    TotalTime='sum(Raw Time)',
                ).transform_calculate(
                    PercentOfTotal="datum['Raw Time'] / datum.TotalTime"
                ).mark_bar(size=50).encode(
                    alt.X('PercentOfTotal:Q',
                    scale=alt.Scale(domain=(0, 1)),
                    axis=alt.Axis(format='.0%', title='Percentage of time in stage')),
                    y='Stage:N'
                ).properties(
                    height=300
                )

    tick = alt.Chart(source).transform_joinaggregate(
        TotalAverages='sum(Averages)',
    ).transform_calculate(
        PercentOfTotalAverages="datum['Averages'] / datum.TotalAverages"
    ).mark_tick(
        color='red',
        thickness=2,
        size=50 * 1,  # controls width of tick.
    ).encode(
        x='PercentOfTotalAverages:Q',
        y='Stage:N'
    )

    text = stage_summary_chart.mark_text(
        align='left',
        baseline='middle',
        dx=20
    ).encode(
        text="Time in stage:N"
    )

    st.altair_chart((stage_summary_chart + tick + text), use_container_width=True)


def plot_stage_timeseries(source:pd.DataFrame):
    stage_timeseries_chart = alt.Chart(source
        ).mark_line(
        ).encode(
            alt.X("dateTime:T",
            axis=alt.Axis(title='Time')),
            alt.Y("stages:Q",
            axis=alt.Axis(tickMinStep=1)),
        )

    # Create a selection that chooses the nearest point & selects based on x-value
    nearest = alt.selection(type='single', nearest=True, on='mouseover',
            fields=['dateTime'], empty='none')

    # Transparent selectors across the chart. This is what tells us
    # the x-value of the cursor
    selectors = alt.Chart(source).mark_point().encode(
        x='dateTime:T',
        opacity=alt.value(0),
    ).add_selection(
        nearest
    )

    # Draw points on the line, and highlight based on selection
    points = stage_timeseries_chart.mark_point().encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )

    # Draw text labels near the points, and highlight based on selection
    text = stage_timeseries_chart.mark_text(align='left', dx=5, dy=-10).encode(
        text=alt.condition(nearest, 'hoursminutes(dateTime):T', alt.value(' '))
    )

    # Draw a rule at the location of the selection
    rules = alt.Chart(source).mark_rule(color='gray').encode(
        x='dateTime:T',
    ).transform_filter(
        nearest
    )

    # Put the five layers into a chart and bind the data
    layers = alt.layer(
        stage_timeseries_chart, selectors, points, rules, text
    ).properties(
        height=300
    )

    st.altair_chart(layers, use_container_width=True)


def plot_heart_timeseries(source:pd.DataFrame):
    heart_timeseries_chart = alt.Chart(source
        ).mark_line(
        ).encode(
            alt.X("time):T",
            axis=alt.Axis(title='Time')),
            alt.Y("value:Q",
            axis=alt.Axis(title='Heart Rate (bpm)')),
        )
    
    st.altair_chart(heart_timeseries_chart, use_container_width=True)


if __name__ == "__main__":

# Setup session state variables
    if "auth_expand" not in st.session_state:
        st.session_state.auth_expand = True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False


    # Setup sidebar
    st.sidebar.header("Settings")
    st.sidebar.subheader("Authentication Status:")
    display_auth_status(st.session_state.authenticated)
    st.session_state.date = st.sidebar.date_input("Date")

    st.title("Fitbit Data Explorer")

    st.header("API Authentication")

    st.write("""Start by authenticating with the Fitbit Web API. 
            \nIf you don't have API credentials, you can obtain them here https://dev.fitbit.com/login""")


    # API Authentication
    with st.beta_expander("Submit API Credentials", expanded=st.session_state.auth_expand):
        with st.form("api_authentication"):
            CLIENT_ID = st.text_input("Enter client ID:")
            CLIENT_SECRET = st.text_input("Enter client secret:")

            # TODO - Remove these before commiting
            CLIENT_ID = '22BP8F'
            CLIENT_SECRET = '0769ad4ba67b091c37f1f07b1cd7c9ac'

            if st.form_submit_button("Authenticate"):
                ACCESS_TOKEN, REFRESH_TOKEN = authenticate(CLIENT_ID, CLIENT_SECRET)
                st.session_state.client = build_client(ACCESS_TOKEN, REFRESH_TOKEN)
                st.session_state.authenticated = True
                st.session_state.auth_expand = False
                # Force rerun to update state on interactive widgets
                st.experimental_rerun()


    if "client" in st.session_state:
        
        # USER INFORMATION
        st.header("User Information")
        with st.beta_expander("", expanded=False):
            user_data = get_user_data(st.session_state.client)

            st.markdown(f"**Name:** {user_data['fullName']}")
            st.markdown(f"**Date of Birth:** {format_dob(user_data['dateOfBirth'])}")
            st.markdown(f"**Age:** {user_data['age']}")
            st.markdown(f"**Height:** {round(user_data['height']*2.54, 1)}cm")
            st.markdown(f"**Weight:** {round(user_data['weight']/2.205, 1)}kg")


        # SLEEP
        st.header("Sleep")
        with st.beta_expander("", expanded=True):

            sleep_data = get_sleep_data(st.session_state.client, st.session_state.date)

            if len(sleep_data["sleep"]) == 0:
                st.warning("No sleep data has been recorded for this day.")
            else:
                sleep_stages = sleep_data['sleep'][0]['levels']['data']
                sleep_stages_df = pd.DataFrame(sleep_stages)
                sleep_summary = sleep_data['summary']
                
                ## Sleep Stats
                bed_time = format_sleep_time_limits(sleep_data['sleep'][0]['startTime'])
                wake_time = format_sleep_time_limits(sleep_data['sleep'][0]['endTime'])
                sleep_delta = str(wake_time - bed_time - timedelta(minutes=sleep_summary['stages']['wake'])).split(':')
                time_asleep = f"{sleep_delta[0]}h {sleep_delta[1]}m"

                st.subheader("Sleep Summary")
                st.text("")

                sleep_col1, sleep_col2, sleep_col3 = st.beta_columns(3)

                with sleep_col1:
                    st.markdown(f"![Moon](https://img.icons8.com/color/48/000000/moon-satellite.png) **Bedtime:** {datetime.strftime(bed_time, '%H:%M')}")
                with sleep_col2:
                    st.markdown(f"![Sun](https://img.icons8.com/color/48/000000/sun--v1.png)**Wakeup:** {datetime.strftime(wake_time, '%H:%M')}")
                with sleep_col3:
                    st.markdown(f"![Time Asleep](https://img.icons8.com/color/48/000000/bed.png) **Time Asleep:** {time_asleep}")

                ## Sleep Stage Summary
                st.markdown("---")
                st.subheader("Sleep Stages")
                st.text("")
                
                time_format = "{:01d}hrs {:02d}min"
                stages = ["wake", "rem", "light", "deep"]

                stage_percentages = {stage: calc_percentage(sleep_summary['stages'][stage], sleep_summary['totalTimeInBed']) for stage in stages}
                raw_stage_times = {stage: sleep_summary['stages'][stage] for stage in stages}
                stage_times = {stage: format_time_in_stage(time_format, sleep_summary['stages'][stage]) for stage in stages}
                stage_avgs = {stage: calc_percentage(get_30_day_avg(stage), sleep_summary['totalTimeInBed']) for stage in stages}

                stage_summary_df = pd.DataFrame.from_dict({
                    'Stage': stage_percentages.keys(), 
                    'Percentage of time in stage': stage_percentages.values(),
                    'Time in stage': stage_times.values(),
                    'Raw Time': raw_stage_times.values(),
                    'Averages': stage_avgs.values()
                    })

                plot_stage_summary(stage_summary_df)

                ## Sleep Stage Timeseries
                st.markdown("---")
                st.subheader("Sleep Timeseries")
                st.text("")

                ### Create a copy of the DataFrame for our time-series analysis
                sleep_timeseries_df = sleep_stages_df.copy()

                final_interval = int(sleep_timeseries_df['seconds'].iloc[-1])
                penultimate_epoch = datetime.strptime(sleep_timeseries_df['dateTime'].iloc[-1], '%Y-%m-%dT%H:%M:%S.%f')
                final_epoch = penultimate_epoch + timedelta(seconds = final_interval)
                new_row = {'dateTime': final_epoch, 'level': 'wake', 'seconds': 0}

                sleep_timeseries_df = sleep_timeseries_df.append(new_row, ignore_index = True)
                sleep_timeseries_df.dateTime = pd.to_datetime(sleep_timeseries_df.dateTime)
                sleep_timeseries_df.set_index('dateTime', inplace=True)
                sleep_timeseries_df = sleep_timeseries_df.resample(rule='30S').ffill()
                sleep_timeseries_df.reset_index(inplace=True)
                sleep_timeseries_df['stages'] = sleep_timeseries_df['level'].map({'deep': 0, 'light': 1, 'rem': 2, 'wake': 3})

                plot_stage_timeseries(sleep_timeseries_df)

                 ### Define time range for night time heart rate analysis
                sleep_start_time = sleep_timeseries_df['dateTime'].iloc[0]
                sleep_end_time = sleep_timeseries_df['dateTime'].iloc[-1]


        # HEART RATE
        st.header("Heart Rate")
        with st.beta_expander("", expanded=False):

            heart_data = get_heart_data(st.session_state.client, st.session_state.date)

            heart_timeseries_data = heart_data['activities-heart-intraday']['dataset']

            if len(heart_timeseries_data) == 0:
                st.warning("No heart rate data has been recorded for this day.")
            else:
                heart_timeseries_df = pd.DataFrame(heart_timeseries_data)
                
                ## Heart Rate Summary
                st.subheader("Heart Rate Summary")
                st.text("")

                heart_col1, heart_col2, heart_col3 = st.beta_columns(3)

                resting_rate = heart_data['activities-heart'][0]['value']['restingHeartRate']

                with heart_col1:
                    st.markdown(f"![Resting](https://img.icons8.com/dotty/48/000000/pulse.png) **Resting Rate:** {resting_rate}")
                with heart_col2:
                    st.markdown(f"![Minimum](https://img.icons8.com/ios/48/000000/minimum-value--v1.png)**Daily Minimum:** {0}")
                with heart_col3:
                    st.markdown(f"![Maximum](https://img.icons8.com/ios/48/000000/maximum-value--v1.png) **Daily Maximum:** {0}")

                ## Heart Rate Timeseries
                st.markdown("---")
                st.subheader("Heart Rate Timeseries")
                st.text("")  

                

                plot_heart_timeseries(heart_timeseries_df)