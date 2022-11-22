

// include the SPI library:
#include <SPI.h>


// set pin 10 as the slave select for the digital pot:
const int slaveSelectPin = 10;
const int slaveReadyPin = 35;

uint8_t data;



void setup() {
  Serial.begin(115200);
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (2, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (slaveReadyPin, INPUT);
  digitalWrite (slaveSelectPin, HIGH);
  SPI.begin(); 

  delay(1000);


  sendWriteSPI(0x40004005,0x60,0x61);       //Select signal generator system as active input for X and Y axis.
  sendWriteSPI(0x40024007,0xC0,0xC0);       //Activate closed loop control for both axes
  sendWriteSPI(0x60006001,0x02,0x02);       //Configure both axes signal unit (02: XY units; 01: OF units; 00: current) OF = optical feedback
  sendWriteSPI(0x60026102,0x00,0x00);       //Configure signal shape (04: Pulse; 03: sawtooth; 02: Square; 01: Triangle; 00: sinusolidal)
  uint32_t X_freq = generateSPFPR(5.0);
  uint32_t Y_freq = generateSPFPR(5.0);
  sendWriteSPI(0x60036103,X_freq,Y_freq);   //Configure frequencies (Single point floating representations)
  uint32_t X_amp = generateSPFPR(0.3);
  uint32_t Y_amp = generateSPFPR(0.05);
  sendWriteSPI(0x60046104,X_amp,Y_amp);     //Configure Amplitudes (Single point floating representations)
  uint32_t Y_phase = generateSPFPR(1.571);  //90deg
  sendWriteSPI(0x60066106,0x00,Y_phase);    //Configure Phase (Radians)(Single point floating representations)
  sendWriteSPI(0x60076107,0x0001,0x0001);   //Cycles (int) - 0x8001 = (dec)-1 = infinte
  sendWriteSPI(0x60096109,0x01,0x01);       //external trigger
  sendWriteSPI(0x60016101,0x01,0x01);       //Set run flag
}


void loop() {


  delay(1000);
  sendReadSPI(0x2201);       //request temp of board
  Serial.println("");
  //sendWriteSPI(0x60016101,0x01,0x01);       //Set run flag
  digitalWrite(2,1);
  delay(1);
  digitalWrite(2,0);
}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){

  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}

void sendReadSPI(uint32_t Register){
  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
  SPI.transfer(0x00);SPI.transfer(0x00);     //read command
  SPI.transfer((Register >> 8) & 0xFF);      //register to read from byte 1
  SPI.transfer((Register) & 0xFF);           //register to read from byte 2
  for(int i=0;i<10;i++){
    data = SPI.transfer(0x00);               //send blank data bytes to fill the rest of the frame
    if(i==1){Serial.print(data);Serial.print("\t");}
  }
  
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
}


uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0) 
    return 0; //handle this special case
  //check sign and begin normalization
  if (f < 0) { 
    sign = 1; 
    normalized = -f; 
  } else { 
    sign = 0; 
    normalized = f; 
  }
  //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { 
    normalized /= 2.0; 
    shift++; 
  }
  while (normalized < 1.0) { 
    normalized *= 2.0; 
    shift--; 
  }
  normalized = normalized - 1.0;
  //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
  //get biased exponent
  exponent = shift + 0x7f; //shift + bias
  //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}
