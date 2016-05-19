from setuptools import setup, find_packages


setup(
    name='dug',
    url='https://github.com/bwhmather/python-dug',
    version='0.1.0',
    author='Ben Mather',
    author_email='bwhmather@bwhmather.com',
    maintainer='',
    license='BSD',
    description='A python memoisation framework',
    long_description=__doc__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=[
    ],
    packages=find_packages(),
    package_data={
        '': ['*.*'],
    },
    test_suite='dug.tests.suite',
)
