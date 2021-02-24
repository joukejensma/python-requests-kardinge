import requests
import json
import datetime
import configparser
import sys
import time

urls =  {
            'FrontendAvailableDatesRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/FrontendAvailableDatesRequest',
            'Auth' : 'https://sport050.bspaas.nl/frontend/json/reply/Authenticate',
            'FrontendDurationRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/FrontendDurationRequest',
            'FrontendReservationExpanded' : 'https://sport050.bspaas.nl/frontend/json/reply/FrontendReservationExpanded',
            'UpsellMeans' : 'https://sport050.bspaas.nl/frontend/json/reply/AddUpsellMeansToReservationRequest',
            'CompleteReservationRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/CompleteReservationRequest',
            'BasketCheckoutRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/BasketCheckoutRequest',
            'FrontendReservationsByDateRangeRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/FrontendReservationsByDateRangeRequest',
            'AvailableTimeBlocksRequest' : 'https://sport050.bspaas.nl/frontend/json/reply/AvailableTimeBlocksRequest',
        }

def setParams(now, config):
    weekAhead = now + datetime.timedelta(weeks=1)

    return {  
            'Auth' : 
                {
                    'UserName' : config['generic']['UserName'],
                    'Password' : config['generic']['Password'],
                },
            'FrontendAvailableDatesRequest' :
                { 
                    'ArrangementID' : None,
                    'ActivityID' : 140, # 140 is schaatsen, 141 ijshockey
                    'LocationID' : None,
                    'MinDate' : now.isoformat(),
                    'MaxDate' : weekAhead.isoformat(),
                    'PersonCount' : None,
                },
            'FrontendDurationRequest' : 
                {
                    'ActivityID' : 140,
                    'ArrangementID' : '0',
                    'LocationID' : 22,
                    'LotID' : None,
                    'StartDateTime' : '2020-12-13T09:30:00.000Z',
                },
            'FrontendReservationExpanded' :
                { 
                    'ID' : None,
                    'ActivityID' : 140,
                    'ArrangementID' : 0,
                    'RepetitionAmount' : None,
                    'RepetitionMode' : None,
                    'LocationID' : 22,
                    'TimeBlocks' : [{'From':'2020-12-13T10:30:00.0000000+01:00','Until':'2020-12-13T11:30:00.0000000+01:00','Available':'true','AvailablePersons':2,'$$hashKey':'object:1114'}],
                    'PersonCount' : 1,
                    'ReservationTypeID':None
                },
            'UpsellMeans' : 
                {
                    'Means' : '[]',
                },
            'CompleteReservationRequest' : 
                {
                },
            'BasketCheckoutRequest' :
                {
                    'PaymentMethodID' : 7,
                    'CustomerReference' : None,
                    'PaymentProviderReturnUrl' : 'https://sport050.bspaas.nl/portal/paymentinfo/',
                },
            'FrontendReservationsByDateRangeRequest' :
                {
                    'StartDate' : now.isoformat(),
                    'EndDate' : weekAhead.isoformat(),
                },
            'AvailableTimeBlocksRequest' : 
                {
                    'ActivityID' : 140,
                    'ArrangementID' : 0,
                    'PersonCount' : 1,
                    'Date' : '2020-12-16T11%3A39%3A36.518Z',
                    'LocationID' : 22,
                },
        }

def listDatesBooked(s, urls, params):
    # date is string in format YYYY-MM-DD
    # return list of dates booked in same format
    dateformat = 'YYYY-MM-DD'

    bookings = s.get(url=urls['FrontendReservationsByDateRangeRequest'], params=params['FrontendReservationsByDateRangeRequest']).json()

    assert 'Items' in bookings, "Key Items komt niet voor in bookings!"

    bookings = bookings['Items']

    datesBooked = [booking['Start'][:len(dateformat)] for booking in bookings]
    
    return datesBooked

def listDatesToBook(config):
    # return list of all sections in config not equal to generic and for which enabled=True

    datesToBook = []
    for section in config.sections():
        if section == 'generic':
            pass
        else:
            if config[section]['enabled'] == 'True':
                datesToBook.append(section)

    return datesToBook

def disableBookedDates(config, listDatesBooked, listDatesToBook):
    for dateToBook in listDatesToBook:
        if dateToBook in listDatesBooked:
            config[dateToBook]['enabled'] = 'False'

            listDatesToBook.remove(dateToBook)
            print(f"Removing {dateToBook} as this date already has a booking!")

    with open(sys.argv[1], 'w') as f:
        config.write(f)

def doBooking(config, now):
    with requests.Session() as s:
        s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0'})

        # timeout to set connection and read from page (separate)
        req_timeout = int(config['generic']['requests_timeout'])

        params = setParams(now, config)

        # Authenticate
        auth = s.post(urls['Auth'], data = params['Auth'], timeout=req_timeout).json()

        avail_days = s.post(url=urls['FrontendAvailableDatesRequest'], data=json.dumps(params['FrontendAvailableDatesRequest']), timeout=req_timeout).json()
        avail_days = [day[:len('YYYY-MM-DD')] for day in avail_days]
        # print(f"Available days: {avail_days}")

        for availableDay in avail_days:
            if availableDay not in config.sections():
                break

            params['AvailableTimeBlocksRequest']['Date'] = f'{availableDay}T01:00:00.000Z'
            avail_times = s.get(url=urls['AvailableTimeBlocksRequest'], params=params['AvailableTimeBlocksRequest']).json()
            avail_times_at_day = [e['From'][len('YYYY-MM-DDT'):len('YYYY-MM-DDT00:00')] for e in avail_times[0]['Blocks'] if (e['Available'] == True) and (e['AvailablePersons'] >= int(config[availableDay]['numberofpersons']))]

            print(f"Checking data for {availableDay} in list {avail_days}, times available are {avail_times_at_day}")

            # print(f"Times available on {availableDay}: {avail_times_at_day}")

            if(len(set(avail_times_at_day).intersection(set(config.getlist(availableDay, 'preferredtimes')))) == 0.):
                # print(f"Requested dates not available at {availableDay}! Exiting...")
                break
            
            # preferred times are given by config[availableDay]['preferredtimes']
            for time in config.getlist(availableDay, 'preferredtimes'):
                if time in avail_times_at_day:
                    print(f"Found available timeslot at {availableDay}T{time}!")
                    break

            time_next = datetime.datetime.strftime(datetime.datetime.strptime(time, '%H:%M') + datetime.timedelta(hours=1), '%H:%M')
            params['FrontendReservationExpanded']['TimeBlocks'] = [{'From' : f'{availableDay}T{time}:00.0000000+01:00',
                                                                    'Until' : f'{availableDay}T{time_next}:00.0000000+01:00',
                                                                    'Available' : 'true',
                                                                    'AvailablePersons' : config[availableDay]['numberofpersons'],
                                                                    '$$hashKey':'object:1114'}]

            params['FrontendReservationExpanded']['PersonCount'] = config[availableDay]['numberofpersons']
            resv_exp = s.post(url=urls['FrontendReservationExpanded'], data=json.dumps(params['FrontendReservationExpanded']), timeout=req_timeout).json()

            complete_resv = s.post(url=urls['CompleteReservationRequest'], data=json.dumps(params['CompleteReservationRequest']), timeout=req_timeout).text

            booking_result = s.post(url=urls['BasketCheckoutRequest'], data=json.dumps(params['BasketCheckoutRequest']), timeout=req_timeout).json()
            print("Final booking...!")

            datesBooked = listDatesBooked(s, urls, params)
            print(f"Dates currently booked: {datesBooked}")

            if(availableDay in datesBooked):
                print(f"Booking succeeded for {availableDay}!")

                # remove just booked date from list
                datesToBook = listDatesToBook(config)
                
                disableBookedDates(config, datesBooked, datesToBook)

            else:
                print(f"Booking failed for {availableDay}!")

if __name__ == '__main__':
    config = configparser.ConfigParser(converters={'list': lambda x: [i.strip() for i in x.split(',')]})

    while(True):
        now = datetime.datetime.now()
        timeShortDelayStart = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, 0) + datetime.timedelta(days=1) + datetime.timedelta(minutes=-2)
        timeShortDelayEnd = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, 0) + datetime.timedelta(minutes=30)
        now_time_str = datetime.datetime.strftime(now, '%H:%M')

        try:
            config.read(sys.argv[1])
        except:
            raise Exception("Program must be called with valid ini file as argument w/ config!. Error reading config file.")

        try:
            doBooking(config, now)
        except requests.exceptions.Timeout:
            # continue along
            print("Timed out...")
            pass

        if((timeShortDelayStart <= now) | (now <= timeShortDelayEnd)):
            print(f"[{now_time_str}] Sleeping for {config['generic']['sh_timeout']} seconds.")
            time.sleep(int(config['generic']['sh_timeout']))
        else:
            print(f"[{now_time_str}] Sleeping for {config['generic']['timeout']} seconds.")
            time.sleep(int(config['generic']['timeout']))
        
