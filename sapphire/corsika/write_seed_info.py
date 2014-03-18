import os
import os.path
import tables
import glob

from sapphire import corsika

DAT_URL = '/data/hisparc/corsika/data'
OUTPUT_PATH = '/data/hisparc/corsika'


class Simulations(tables.IsDescription):
    """Store information about shower particles reaching ground level"""

    seed1 = tables.UInt32Col(pos=0)
    seed2 = tables.UInt32Col(pos=1)
    particle_id = tables.UInt32Col(pos=2)
    energy = tables.Float32Col(pos=3)
    first_interaction_altitude = tables.Float32Col(pos=4)
    p_x = tables.Float32Col(pos=5)
    p_y = tables.Float32Col(pos=6)
    p_z = tables.Float32Col(pos=7)
    zenith = tables.Float32Col(pos=8)
    azimuth = tables.Float32Col(pos=9)
    observation_height = tables.Float32Col(pos=10)


def save_seed(row, seeds, header):
    """Write the information of a particle into a row"""

    seed1, seed2 = seeds.split('_')
    row['seed1'] = seed1
    row['seed2'] = seed2
    row['particle_id'] = header.particle_id
    row['energy'] = header.energy
    row['first_interaction_altitude'] = header.first_interaction_altitude
    row['p_x'] = header.p_x
    row['p_y'] = header.p_y
    row['p_z'] = header.p_z
    row['zenith'] = header.zenith
    row['azimuth'] = header.azimuth
    row['observation_height'] = header.observation_heights[0]
    row.append()


def write_row(output_row, seeds):
    """Read the header of a simulation and write this to the output."""

    with tables.openFile(os.path.join(DAT_URL, seeds, 'corsika.h5'),
                         'r') as corsika_data:
        header = corsika_data.root.groundparticles._v_attrs.event_header

    save_seed(output_row, seeds, header)


def get_simulations(simulations_data):
    """Get the information of the simulations and create a table."""

    files = glob.glob(os.path.join(DAT_URL, '*/corsika.h5'))
    simulations_table = simulations_data.getNode('/simulations')
    for file in files:
        output_row = simulations_table.row
        os.path.dirname(file)
        dir = os.path.dirname(file)
        seeds = os.path.basename(dir)
        write_row(output_row, seeds)
    simulations_table.flush()


def prepare_output():
    """Write the table to seed_info.h5"""

    simulations_data = tables.openFile(os.path.join(OUTPUT_PATH,
                                                    'seed_info.h5'), 'w')
    simulations_data.createTable('/', 'simulations', Simulations,
                                 'Simulations overview')
    return simulations_data


def main():
    simulations_data = prepare_output()
    get_simulations(simulations_data)
    simulations_data.close()


if __name__ == '__main__':
    simulation_info = main()
