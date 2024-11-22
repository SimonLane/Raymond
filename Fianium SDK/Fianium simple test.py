from NKTP_DLL import *
from time import sleep


# Open the COM port
# Not nessesary, but would speed up the communication, since the functions does
# not have to open and close the port on each call
openResult = openPorts('COM5', 0, 0)
print('Opening the comport:', PortResultTypes(openResult))

# Example - Reading of the Firmware Revision register 0x64(regId) in BASIK (K1x2) at address 8 (devId)
# index = 2, because the str starts at byte index 2
rdResult, FWVersionStr = registerReadAscii('COM5', 15, 0x65, 2)
print('Reading firmware version str:', FWVersionStr, RegisterResultTypes(rdResult))

# Example - Turn on emission on BASIK (K1x2) by setting register 0x30 = 1
# See SDK Instruction Manual page 41
wrResult = registerWriteU8('COM5', 15, 0x30, 3, -1) 
print('Turn on emission:', RegisterResultTypes(rdResult))

print('sleeping for 4 seconds')
sleep(4.0)

# Example get serial number str
rdResult, serial = deviceGetModuleSerialNumberStr('COM5', 15)
print('Serial:', serial, DeviceResultTypes(rdResult))
     

#Turn on RF power by setting register 0x30 = 1
# See SDK Instruction Manual page 41
wrResult = registerWriteU8('COM5', 17, 0x30, 1, -1) 
print('Turn on RF power:', RegisterResultTypes(rdResult))

# Read Crystal temp
rdResult, FWVersionStr = registerRead('COM5', 17, 0x38, -1)
print('Reading crystal temp:', FWVersionStr, RegisterResultTypes(rdResult))

# convert output to decimal
decimal_value = int.from_bytes(FWVersionStr[:1], byteorder='big')
print('temp (C): ', decimal_value/10.0)

# set a wavelength (520.5nm)
result = registerWriteU32('COM5', 17, 0x90, 520500, 0)
print('set Wavelength:', RegisterResultTypes(result))

result, FWVersionStr  = registerReadU32('COM5', 17, 0x90, 0)
print('Reading wavelength:', FWVersionStr/1000, RegisterResultTypes(result))

# set amplitude (52.3%)
result = registerWriteU32('COM5', 17, 0xB0, 523, 0)
print('set Wavelength:', RegisterResultTypes(result))

result, FWVersionStr  = registerReadU32('COM5', 17, 0xB0, 0)
print('Reading power:', FWVersionStr/10, RegisterResultTypes(result))


for i in range(5,0,-1):
    print(i)
    sleep(1)

#Turn off RF power by setting register 0x30 = 1
# See SDK Instruction Manual page 41
wrResult = registerWriteU8('COM5', 17, 0x30, 0, -1) 
print('Turn off RF power:', RegisterResultTypes(rdResult))



# Example - Turn off emission on BASIK (K1x2) by setting register 0x30 = 0
# See SDK Instruction Manual page 41
wrResult = registerWriteU8('COM5', 15, 0x30, 0, -1) 
print('Turn off emission:', RegisterResultTypes(wrResult))

# Close the port
closeResult = closePorts('COM5')
print('Close the comport:', PortResultTypes(closeResult))

