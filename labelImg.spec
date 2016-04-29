# -*- mode: python -*-

block_cipher = None


a = Analysis(['labelImg.py'],
             pathex=['D:\\ComputerTechnology\\labelImg','D:\\ComputerTechnology\\labelImg\\libs'],
             binaries=None,
             datas=None,
             hiddenimports=['lib'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='labelImg',
          debug=False,
          strip=False,
          upx=True,
          console=True )
