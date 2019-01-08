waiting, sel_track_cars, sel_drivers, race = range(4)  # states


def statename(state):
    return ['waiting', 'sel_track_cars', 'sel_drivers', 'race'][state]
