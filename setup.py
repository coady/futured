from setuptools import setup
import futured

setup(
    name='futured',
    version=futured.__version__,
    description='Functional interface for concurrent futures, including asynchronous I/O.',
    long_description=open('README.rst').read(),
    author='Aric Coady',
    author_email='aric.coady@gmail.com',
    url='https://bitbucket.org/coady/futured',
    license='Apache Software License',
    py_modules=['futured'],
    tests_require=['pytest-cov'],
    keywords='concurrent futures threads processes async asyncio',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
