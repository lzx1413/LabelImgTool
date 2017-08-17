
all: resources.py

%.py: %.qrc
	pyrcc4 -o $@ $<

clean:
       rm -f .settings.pkl resources.pyc
