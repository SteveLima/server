from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import cgi


## import CRUD operations from lesson 1 ##
from database_setup import Base, Restaurant, MenuItem
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

## create seesion and connect to database ##
engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()



class webserverHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		if self.path.endswith("/restaurants"):
			restaurants = session.query(Restaurant).all()
			self.send_response(200)
			self.send_header('Content-type', 'text/html')
			self.end_headers()

			output = ""
			output += "<html><body>"
			for restaurant in restaurants:
				output += restaurant.name
				output += "</br>"
				output += " <a href='/restaurants/%s/edit'> edit</a> "%restaurant.id 
				output += "</br>"
				output += "<a href = '/restaurants/%s/delete'> Delete </a> " %restaurant.id
				output += "</br>"
			output += "</br>"
			output += "<a href = '/restaurants/new'> Make a new restaurant </a> "
			output += "</html></body>"

			self.wfile.write(output)
			return

		if self.path.endswith("/new"):
			self.send_response(200)
			self.send_header('Content-type', 'text/html')
			self.end_headers()

			output = ""
			output += "<html><body>"	
			output += "<h2> Insert new restaurant name:</h2>"
			output += '''<form method='POST' enctype='multipart/form-data' action='/restaurants/new'>
			<input name="NewRestaurantName" type="text" ><input type="submit" value="Create"> </form>'''
			output += "</body></html>"
			self.wfile.write(output)

		if self.path.endswith("/edit"):
		    	restaurantIDPath = self.path.split("/")[2]
		        myRestaurantQuery = session.query(Restaurant).filter_by(
		            id=restaurantIDPath).first()

			if myRestaurantQuery :
				self.send_response(200)
				self.send_header('Content-type', 'text/html')
				self.end_headers()

				output = "<html><body>"
				output += "<h2>"
				output += myRestaurantQuery.name
				output += "</h2>"
				output += '''<form method='POST' enctype='multipart/form-data' action='/restaurants/%s/edit'>
				<input name="NewRestaurantName" type="text" ><input type="submit" value="Create"> </form>''' % restaurantIDPath
				output += "</body></html>"
				self.wfile.write(output)
				print output

		if self.path.endswith("/delete"):
			restaurantIDPath = self.path.split("/")[2]
			myRestaurantQuery = session.query(Restaurant).filter_by(id=restaurantIDPath).one()

			if myRestaurantQuery:
				self.send_response(200)
				self.send_header('Content-type', 'text/html')
				self.end_headers()

				output = "<html><body>"
				output += "<h2>"
				output += "Are you sure you want to remove '%s'" % myRestaurantQuery.name
				output += "</h2>"
				output += "</br>"
				output += "<form method ='POST' enctype='multipart/form-data' action='/restaurants/%s/delete'>" % restaurantIDPath
				output += "<input type = 'submit' value='Delete'>"
				output += "</form>"
				output += "</html></body>"
				self.wfile.write(output)
			




	def do_POST(self):
		try:
			if self.path.endswith("/new"):

				ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
				if ctype == 'multipart/form-data':
					fields = cgi.parse_multipart(self.rfile, pdict)
					messagecontent = fields.get('NewRestaurantName')

				NewRestaurant= Restaurant(name = messagecontent[0])
				session.add(NewRestaurant)
				session.commit()

				self.send_response(301)
				self.send_header('Content-Type',   'text/html')
				self.send_header('Location', '/restaurants')
				self.end_headers()

			if self.path.endswith("/edit"):
				ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
				if ctype == 'multipart/form-data':
					fields = cgi.parse_multipart(self.rfile, pdict)
					messagecontent = fields.get('NewRestaurantName')
					restaurantIDPath = self.path.split("/")[2]

					myRestaurantQuery = session.query(Restaurant).filter_by(
		            	id=restaurantIDPath).first()

					if myRestaurantQuery:
						myRestaurantQuery.name = messagecontent[0]
						session.add(myRestaurantQuery)
						session.commit()

						self.send_response(301)
						self.send_header('Content-Type',   'text/html')
						self.send_header('Location', '/restaurants')
						self.end_headers()


			if self.path.endswith("/delete"):
				ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
				
				restaurantIDPath = self.path.split("/")[2]

				myRestaurantQuery = session.query(Restaurant).filter_by(
	            	id=restaurantIDPath).one()

				if myRestaurantQuery:
					session.delete(myRestaurantQuery)
					session.commit()
					self.send_response(301)
					self.send_header('Content-Type',   'text/html')
					self.send_header('Location', '/restaurants')
					self.end_headers()


			return

		except:
			pass


def main():
	try:
		port = 8080
		server = HTTPServer(('', port), webserverHandler)
		print "web server running on port %s" % port
		server.serve_forever()

	except KeyboardInterrupt:
		print "^C entered, stopping web server..."
		server.socket.close()

if __name__ == '__main__':
	main()