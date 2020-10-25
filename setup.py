from setuptools import setup
import futured

setup(
    name='futured',
    version=futured.__version__,
    description='Functional interface for concurrent futures, including asynchronous I/O.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Aric Coady',
    author_email='aric.coady@gmail.com',
    url='https://github.com/coady/futured',
    project_urls={'Documentation': 'https://coady.github.io/futured'},
    license='Apache Software License',
    py_modules=['futured'],
    extras_require={'docs': open('docs/requirements.txt').read().splitlines()},
    python_requires='>=3.6',
    tests_require=['pytest-cov', 'pytest-parametrized'],
    keywords='concurrent futures threads processes async asyncio',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
