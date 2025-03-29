# PySafe


An Alternative File Upload Service written in Python meant to replace
Anonfiles and a few other dead services such as `zz.fo` & `bayfiles`.

## Our Goals
- Making sure that hosters have zero surprises when using this program to host files. Meaning that very few errors or issues should ever arise.

- Providing alternatives to other File Hosting services by keeping the requirements for running it very minimal & small.

- Making better services than the dead ones that came before this one.

- Nothing more than python 3.9+ aiohttp, sqlalchemy, yaml and msgspec

- Batteries included, And My Personal Asynchronous Tor library is also included.

- Until Arti's Tor-Hidden-Service Features are fully stable and all the security features have been added, We will stick to using python and maintaining this branch. It is my plan to swap to rust after this gets done so that the only thing we will need is the exe and a few files. You won't need to install tor at that point to host a hidden-service with it and the ideas with using tor will be endless by that point.

- Limiting the requirements of what is needed compared to other open source hosting services. Example: "You need Node-js and this specific version of yarn with this version of..." The list goes on. The goal is to put an end to that logic once and for all...


## Pull Requests

I encourage anybody to make pull requests. We need to implement a few more items such as

- Progressbar for files being uploaded via dropzone.
- Noscript.html for older operating systems.
- Url proxying by requesting for different files with aiohttp_socks (We don't want the hoster's IP leaked if were using tor...)
- Adding an optional feature to blacklist filetypes such as .exe
- Maybe a Host/Admin Portal for editing css files and reviewing files that may need removing such as malware and nono-materials.


## Currently Supports
It is my priority to make all operating systems that can run python 3.9 or higher are all supported
- [x] Windows
- [ ] Linux (Needs tesing on linux) however feel free to report to me if you bump into an error and we can try to fix it.
- [ ] Apple MacOS
- [ ] Android
